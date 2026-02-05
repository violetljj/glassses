"""
OmniService: 封装 qwen3-omni-flash-realtime 多模态实时对话
统一处理语音输入、语音输出和图像理解
"""
import os
import base64
import threading
import queue
import time
import cv2

import dashscope
from dashscope.audio.qwen_omni import (
    OmniRealtimeConversation, 
    OmniRealtimeCallback,
    MultiModality,
    AudioFormat
)

from . import config
from .state import AppState
from .audio_service import AudioService


class OmniService:
    """
    Qwen3-Omni-Flash-Realtime 服务
    - 实时语音识别 (内置 VAD)
    - 实时语音合成
    - 图像理解
    """
    
    def __init__(self, state: AppState, audio_svc: AudioService):
        self.state = state
        self.audio = audio_svc
        self.conversation = None
        self.connected = False
        
        # 音频输出缓冲
        self.audio_buffer = queue.Queue()
        
        # 配置 DashScope API Key
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            dashscope.api_key = api_key
            print("OmniService: DashScope API Key configured.")
        else:
            print("OmniService: WARNING - API Key not found!")
        
        # 启动音频播放线程
        self._audio_thread = threading.Thread(target=self._audio_player_loop, daemon=True)
        self._audio_thread.start()
    
    def connect(self):
        """建立 WebSocket 连接"""
        if self.connected:
            return
        
        try:
            callback = self._create_callback()
            
            self.conversation = OmniRealtimeConversation(
                model='qwen3-omni-flash-realtime',
                callback=callback,
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
            )
            
            self.conversation.connect()
            output_format = (
                AudioFormat.PCM_16000HZ_MONO_16BIT
                if config.OMNI_OUTPUT_HZ == 16000
                else AudioFormat.PCM_24000HZ_MONO_16BIT
            )
            self.conversation.update_session(
                output_modalities=[MultiModality.AUDIO, MultiModality.TEXT],
                voice='Chelsie',  # 音色选择
                input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
                output_audio_format=output_format,
                enable_input_audio_transcription=True,
                input_audio_transcription_model='gummy-realtime-v1',
                enable_turn_detection=True,
                turn_detection_type='server_vad',
            )
            
            self.connected = True
            print("OmniService: Connected to qwen3-omni-flash-realtime")
            print(f"OmniService: audio output {config.OMNI_OUTPUT_HZ} Hz -> target {config.OMNI_TARGET_HZ} Hz")
            
        except Exception as e:
            print(f"OmniService: Connection failed: {e}")
            self.connected = False
    
    def disconnect(self):
        """断开连接"""
        if self.conversation:
            try:
                self.conversation.close()
            except:
                pass
        self.connected = False
        print("OmniService: Disconnected")
    
    def append_audio(self, pcm_data: bytes):
        """
        推送音频数据到 Omni
        pcm_data: 16kHz, 16bit, mono PCM
        """
        if not self.connected or not self.conversation:
            return
        
        try:
            audio_b64 = base64.b64encode(pcm_data).decode('ascii')
            self.conversation.append_audio(audio_b64)
        except Exception as e:
            print(f"OmniService: Failed to append audio: {e}")
            self._try_reconnect()
    
    def append_image(self):
        """
        附加当前摄像头画面到对话
        使用 append_video 方法发送单帧图像
        """
        if not self.connected or not self.conversation:
            return
        
        frame, _ = self.state.get_frame()
        if frame is None:
            print("OmniService: No frame available")
            return
        
        try:
            # 压缩图片
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            jpg_b64 = base64.b64encode(buffer).decode('utf-8')
            
            # 使用 append_video 发送图像帧
            self.conversation.append_video(jpg_b64)
            print("OmniService: Image frame sent to conversation")
            
        except Exception as e:
            print(f"OmniService: Failed to send image: {e}")
    
    def _create_callback(self):
        """创建回调处理器"""
        service = self
        
        class OmniCallback(OmniRealtimeCallback):
            def on_open(self) -> None:
                print("OmniService: WebSocket opened")
            
            def on_close(self, close_status_code, close_msg) -> None:
                print(f"OmniService: WebSocket closed ({close_status_code}): {close_msg}")
                service.connected = False
            
            def on_event(self, response: dict) -> None:
                try:
                    resp_type = response.get('type', '')
                    
                    if resp_type == 'session.created':
                        session_id = response.get('session', {}).get('id', 'unknown')
                        print(f"OmniService: Session created: {session_id}")
                    
                    elif resp_type == 'input_audio_buffer.speech_started':
                        # VAD 检测到说话开始，打断当前播放
                        print("[Omni] VAD: Speech started")
                        service._cancel_playback()
                        service.state.update_voice_state("listening")
                        
                        # 立即发送当前画面，让 AI 在回答前就能看到
                        service.append_image()
                    
                    elif resp_type == 'input_audio_buffer.speech_stopped':
                        print("[Omni] VAD: Speech stopped")
                        service.state.update_voice_state("processing")
                    
                    elif resp_type == 'conversation.item.input_audio_transcription.completed':
                        # 用户语音转文字完成
                        transcript = response.get('transcript', '')
                        if transcript:
                            print(f"[Omni] User: {transcript}")
                            service.state.add_voice_log("user", transcript)
                    
                    elif resp_type == 'response.audio_transcript.delta':
                        # AI 回复文字
                        text = response.get('delta', '')
                        if text:
                            print(f"[Omni] AI: {text}", end='', flush=True)
                    
                    elif resp_type == 'response.audio.delta':
                        # AI 回复音频
                        audio_b64 = response.get('delta', '')
                        if audio_b64:
                            service.audio_buffer.put(base64.b64decode(audio_b64))
                            service.state.update_voice_state("speaking")
                    
                    elif resp_type == 'response.done':
                        print("\n[Omni] Response complete")
                        # 获取完整回复文本
                        # service.state.add_voice_log("ai", full_text)
                        
                    elif resp_type == 'error':
                        error_msg = response.get('message', 'Unknown error')
                        print(f"[Omni] Error: {error_msg}")
                        
                except Exception as e:
                    print(f"[Omni] Callback error: {e}")
        
        return OmniCallback()
    
    def _audio_player_loop(self):
        """Audio playback loop: send buffered audio to ESP32."""
        import audioop

        out_hz = getattr(config, "OMNI_OUTPUT_HZ", 24000)
        target_hz = getattr(config, "OMNI_TARGET_HZ", 16000)
        bytes_per_sec = out_hz * 2  # 16bit mono
        MIN_CHUNK_BYTES = max(bytes_per_sec // 2, 1024)

        accumulated = b''
        last_data_time = 0
        resample_state = None

        while True:
            try:
                # ????????????
                try:
                    chunk = self.audio_buffer.get(timeout=0.1)
                    accumulated += chunk
                    last_data_time = time.time()
                except queue.Empty:
                    pass

                # ????????
                # 1. ????????? OR
                # 2. ????????? 0.3 ??????????????????????????
                should_send = False
                ended_by_timeout = False
                if accumulated:
                    if len(accumulated) >= MIN_CHUNK_BYTES:
                        should_send = True
                    elif last_data_time > 0 and (time.time() - last_data_time) > 0.3:
                        should_send = True
                        ended_by_timeout = True

                if should_send:
                    if out_hz != target_hz:
                        try:
                            resampled, resample_state = audioop.ratecv(
                                accumulated, 2, 1, out_hz, target_hz, resample_state
                            )
                            self.audio.play_pcm_bytes(resampled, sample_rate=target_hz)
                        except Exception as e:
                            print(f"[Omni] Resample Error: {e}")
                            self.audio.play_pcm_bytes(accumulated, sample_rate=out_hz)
                    else:
                        self.audio.play_pcm_bytes(accumulated, sample_rate=out_hz)

                    accumulated = b''
                    last_data_time = 0
                    if ended_by_timeout:
                        resample_state = None

            except Exception as e:
                print(f"OmniService: Audio player error: {e}")
                time.sleep(0.1)

    def _cancel_playback(self):
        """取消当前播放"""
        # 清空音频缓冲
        while not self.audio_buffer.empty():
            try:
                self.audio_buffer.get_nowait()
            except queue.Empty:
                break
    
    def _try_reconnect(self):
        """尝试重新连接"""
        if not self.connected:
            print("OmniService: Attempting to reconnect...")
            self.connect()