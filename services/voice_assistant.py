import os
import concurrent.futures
import threading
import time
import asyncio
import queue
import edge_tts
import cv2
import base64
from http import HTTPStatus
from pathlib import Path
from openai import OpenAI
from PIL import Image
from typing import Optional

from . import config
from .state import AppState
from .audio_service import AudioService
import re

# 阿里云 DashScope ASR
try:
    import dashscope
    from dashscope.audio.asr import Recognition
    # Qwen-TTS-Realtime imports
    from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat
    DASHSCOPE_ASR_AVAILABLE = True
except ImportError:
    DASHSCOPE_ASR_AVAILABLE = False
    print("Warning: dashscope not installed, fallback to Google STT")

# ==============================================================================
# Qwen-TTS-Realtime Callback (Module Level)
# ==============================================================================
if DASHSCOPE_ASR_AVAILABLE:
    class _QwenTTSCallback(QwenTtsRealtimeCallback):
        def __init__(self):
            super().__init__()
            self.complete_event = threading.Event()
            self.audio_buffer = bytearray()
            self.error_msg = None

        def on_open(self) -> None:
            pass

        def on_close(self, close_status_code, close_msg) -> None:
            pass

        def on_event(self, response) -> None:
            try:
                # Support both dict and object access
                if isinstance(response, dict):
                    event_type = response.get('type')
                    delta = response.get('delta')
                else:
                    event_type = getattr(response, 'type', '')
                    delta = getattr(response, 'delta', None)

                if event_type == 'response.audio.delta' and delta:
                    self.audio_buffer.extend(base64.b64decode(delta))
                elif event_type == 'session.finished':
                    self.complete_event.set()
                elif event_type == 'error':
                    self.error_msg = str(response)
                    self.complete_event.set()
            except Exception as e:
                print(f"QwenTTS callback error: {e}")
                self.error_msg = str(e)
                self.complete_event.set()

        def wait_for_finished(self, timeout: int = 10) -> bool:
            return self.complete_event.wait(timeout)

class VoiceAssistant:
    def __init__(self, state: AppState, audio_svc: AudioService):
        self.state = state
        self.audio = audio_svc
        
        # 配置 OpenAI (用于视觉推理)
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        if api_key:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            # 默认使用 Qwen3-VL-Flash (用户请求)
            self.model_name = os.getenv("OPENAI_MODEL", "qwen3-vl-flash")
            print(f"VoiceAssistant: OpenAI/DashScope ready (Model: {self.model_name}).")
            
            # 配置 DashScope ASR (使用相同的 API Key)
            if DASHSCOPE_ASR_AVAILABLE:
                dashscope.api_key = api_key
                print("VoiceAssistant: Aliyun Paraformer ASR ready.")
        else:
            self.client = None
            print("VoiceAssistant: WARNING - OPENAI_API_KEY not found. AI features disabled.")

        # 使用线程安全的队列替代列表
        self.process_queue = queue.Queue()
        
        # 线程池用于并发执行 Vision 请求
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # 启动处理线程
        threading.Thread(target=self._worker, daemon=True).start()

    def on_recording_complete(self, wav_path: Path):
        """当麦克风服务完成一段录音时调用"""
        if not wav_path.exists(): return
        
        self.process_queue.put(wav_path)
        self.state.update_voice_state("processing")

    def _worker(self) -> None:
        while True:
            try:
                # 阻塞等待，超时 0.5 秒以便定期检查
                target_wav = self.process_queue.get(timeout=0.5)
            except queue.Empty:
                continue
                
            self._process_audio(target_wav)
            self.process_queue.task_done()

    def _recognize_with_aliyun(self, wav_path: Path) -> str:
        """使用阿里云 Paraformer 进行语音识别"""
        recognition = Recognition(
            model='paraformer-realtime-v2',
            format='wav',
            sample_rate=16000,
            language_hints=['zh', 'en'],  # 支持中英文
            callback=None  # 同步调用
        )
        
        result = recognition.call(str(wav_path))
        
        if result.status_code == HTTPStatus.OK:
            sentences = result.get_sentence()
            if sentences:
                # 合并所有句子
                if isinstance(sentences, list):
                    return ''.join([s.get('text', '') for s in sentences])
                elif isinstance(sentences, dict):
                    return sentences.get('text', '')
                else:
                    return str(sentences)
        else:
            print(f"Aliyun ASR Error: {result.message}")
        return ""

    def _generate_vision_description(self, frame, prompt: str = "直接描述画面前方的内容，不要包含'这张图片'、'视角'等开场白，不要解释画面质量。重点关注障碍物、人和文字。直接说结果。50字以内。") -> Optional[str]:
        """后台执行的视觉分析任务"""
        print("VoiceAssistant: [Async] Starting Vision Analysis...")
        if not self.client:
            return None
        
        try:
            # 编码图片
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            t0 = time.time()
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{jpg_as_text}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=100
            )
            reply_text = response.choices[0].message.content
            print(f"VoiceAssistant: [Async] Vision Done in {time.time()-t0:.2f}s")
            return reply_text
        except Exception as e:
            print(f"VoiceAssistant: [Async] Vision Error: {e}")
            return None

    def _sanitize_for_tts(self, text: str) -> str:
        """清洗文本，移除 Markdown 符号，使其更适合朗读"""
        import re
        # 移除加粗/斜体标记 (**text**, *text*)
        text = re.sub(r'\*\*|__|\*|_', '', text)
        # 移除列表符号 (- , * )
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
        # 移除标题符号 (# )
        text = re.sub(r'#+\s', '', text)
        # 移除多余空行
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()

    def _process_audio(self, wav_path: Path) -> None:
        """核心处理流程: 并发(Vision, STT) -> 关键词过滤 -> TTS"""
        print(f"VoiceAssistant: Processing {wav_path.name}...")
        
        # 1. 立即获取当前画面并启动 Vision 任务 (Async)
        frame, _ = self.state.get_frame()
        vision_future = None
        
        if frame is not None:
             # 因为我们还没拿到用户的具体问题，所以只能用通用 Prompt
             vision_future = self.executor.submit(self._generate_vision_description, frame)
        else:
             print("VoiceAssistant: No frame available for async vision.")

        text = ""
        
        # 2. 并行执行 Speech To Text
        try:
            t0 = time.time()
            if DASHSCOPE_ASR_AVAILABLE:
                text = self._recognize_with_aliyun(wav_path)
                print(f"[Timing] Aliyun ASR: {time.time()-t0:.2f}s")
            else:
                # Fallback: Google Web Speech API
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                with sr.AudioFile(str(wav_path)) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language="zh-CN")
                print(f"[Timing] Google STT: {time.time()-t0:.2f}s")
            
            if text:
                print(f"User said: {text}")
                self.state.add_voice_log("user", text)
            else:
                print("VoiceAssistant: Could not understand audio")
                # 如果 STT 失败，我们也不播报 Vision 结果了，节省用户困惑
                self.state.update_voice_state("idle")
                return
                
        except Exception as e:
            print(f"VoiceAssistant STT Error: {e}")
            self.state.update_voice_state("idle")
            return
        finally:
            try:
                os.remove(wav_path)
            except:
                pass

        if not text: 
            self.state.update_voice_state("idle")
            return

        # 3. 寻物指令检测 (优先于其他指令)
        if self._parse_stop_search_command(text):
            return
        if self._parse_search_command(text):
            return

        # 3. 关键词检测 & 结果同步
        # 关键词: "看", "描述", "前面", "什么", "读", "识别"
        keywords = ["看", "描述", "前面", "什么", "读", "识别", "在哪"]
        
        # 如果包含关键词，我们去取 Vision 结果并播报
        if any(k in text for k in keywords):
            print("VoiceAssistant: Keywords detected. Waiting for Vision result...")
            
            if vision_future:
                try:
                    # 等待 Vision 结果 (如果 STT 很快，这里会阻塞一会儿；如果 STT 慢，这里可能已经好了)
                    ai_reply = vision_future.result(timeout=10) 
                    
                    if ai_reply:
                        print(f"AI Reply: {ai_reply}")
                        self.state.add_voice_log("ai", ai_reply)
                        
                        # 清洗 Markdown 符号，防止 TTS 读出星号
                        clean_reply = self._sanitize_for_tts(ai_reply)
                        self._speak(clean_reply)
                    else:
                        self._speak("抱歉，我无法看清画面")
                except Exception as e:
                    print(f"VoiceAssistant: Failed to get vision result: {e}")
                    self._speak("视觉服务响应超时")
            else:
                 self._speak("抱歉，没有获取到画面")
        else:
            # 不包含关键词，忽略 Vision 结果 (如果还在跑，它会自己跑完但没人接)
            print("VoiceAssistant: No keyword match. Ignoring vision result.")
            self.state.update_voice_state("idle")

    # =========================
    # 寻物模式指令解析
    # =========================
    def _parse_search_command(self, text: str) -> bool:
        """
        解析寻物指令，格式：'找[物品]' 或 '寻找[物品]' 或 '帮我找[物品]'
        
        Returns:
            True 如果成功解析并启动寻物模式
        """
        # 正则匹配寻物指令
        patterns = [
            r'找(?:一?下)?(.+)',      # "找xxx", "找一下xxx"
            r'寻找(.+)',               # "寻找xxx"
            r'帮我找(.+)',             # "帮我找xxx"
            r'(.+)在哪',               # "xxx在哪"
        ]
        
        item_name = None
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                item_name = match.group(1).strip()
                # 清理常见后缀
                item_name = re.sub(r'[呢呀吗啊呢呢？！\?\.]+$', '', item_name).strip()
                break
        
        if not item_name:
            return False
        
        # 尝试将中文物品名映射到 COCO 类名
        target_class = None
        
        # 1. 精确匹配别名表
        if item_name in config.SEARCH_ALIASES:
            target_class = config.SEARCH_ALIASES[item_name]
        else:
            # 2. 模糊匹配（物品名是别名的子串）
            for alias, coco_name in config.SEARCH_ALIASES.items():
                if alias in item_name or item_name in alias:
                    target_class = coco_name
                    break
        
        # 3. 直接使用英文类名（如果用户说的就是 COCO 类名）
        if not target_class and item_name.lower() in config.SEARCHABLE_CLASSES:
            target_class = item_name.lower()
        
        if target_class:
            self.state.start_search(target_class, item_name)
            self._speak(f"开始寻找{item_name}，请慢慢移动摄像头")
            return True
        else:
            # 无法识别的物品
            self._speak(f"抱歉，我不认识{item_name}，请尝试换个说法")
            return True  # 返回 True 表示已处理，不走后续流程

    def _parse_stop_search_command(self, text: str) -> bool:
        """
        解析停止寻物指令：'停止'/'找到了'/'取消'/'不找了'
        
        Returns:
            True 如果成功解析并停止寻物模式
        """
        # 只有在寻物模式下才响应停止指令
        search_state = self.state.get_search_state()
        if not search_state["active"]:
            return False
        
        stop_keywords = ["停止", "找到了", "取消", "不找了", "结束", "关闭"]
        if any(k in text for k in stop_keywords):
            target_label = search_state["target_label"]
            self.state.stop_search()
            self._speak(f"寻物模式已关闭")
            return True
        
        return False

# ==============================================================================
# Qwen-TTS-Realtime Integration
# ==============================================================================
    def _speak_with_qwen(self, text: str):
        """Use Qwen-TTS-Realtime for speech synthesis (Buffered)"""
        if not DASHSCOPE_ASR_AVAILABLE:
            print("DashScope not available, using EdgeTTS")
            self._speak_edge_tts(text)
            return

        if not text: return
        
        callback = _QwenTTSCallback()
        
        try:
            tts_client = QwenTtsRealtime(
                model='qwen-tts-realtime',
                callback=callback,
                # api_key is auto loaded from dashscope.api_key or env
            )
            
            # Connect
            tts_client.connect()
            
            # Update Session: Voice='Cherry', 16k 16bit mono
            tts_client.update_session(
                voice='Cherry', 
                response_format=AudioFormat.PCM_16000HZ_MONO_16BIT, 
                mode='server_commit'
            )
            
            # Send text
            tts_client.append_text(text)
            
            # Finish and wait
            tts_client.finish()
            
            finished = callback.wait_for_finished(timeout=10)
            
            if not finished:
                print("QwenTTS timeout")
                # Don't return yet, check buffer
                
            if callback.error_msg:
                print(f"QwenTTS API Error: {callback.error_msg}")
                # Fallback?
                self._speak_edge_tts(text)
                return

            if len(callback.audio_buffer) > 0:
                print(f"QwenTTS generated {len(callback.audio_buffer)} bytes. Playing...")
                self.audio.play_pcm_bytes(bytes(callback.audio_buffer), sample_rate=16000)
            else:
                print("QwenTTS: No audio received.")
                self._speak_edge_tts(text)

        except Exception as e:
            print(f"QwenTTS Exception: {e}")
            print("Fallback to EdgeTTS...")
            self._speak_edge_tts(text)

    def _speak(self, text: str) -> None:
        """Unified TTS Entry Point"""
        if not text: return
        
        self.state.update_voice_state("speaking")
        try:
            # Prefer Qwen TTS if available
            if DASHSCOPE_ASR_AVAILABLE and os.getenv("OPENAI_API_KEY"):
               self._speak_with_qwen(text)
            else:
               self._speak_edge_tts(text)
        finally:
            self.state.update_voice_state("idle")

    def _speak_edge_tts(self, text: str) -> None:
        """Edge-TTS Fallback"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            communicate = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
            
            temp_mp3 = Path("temp_tts.mp3")
            loop.run_until_complete(communicate.save(str(temp_mp3)))
            
            from pydub import AudioSegment
            sound = AudioSegment.from_mp3(str(temp_mp3))
            
            sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            pcm_data = sound.raw_data
            
            self.audio.play_pcm_bytes(pcm_data)
            os.remove(temp_mp3)
            
        except Exception as e:
            print(f"EdgeTTS Error: {e}")

