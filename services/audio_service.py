import socket
import wave
import queue
import threading
import time
import numpy as np
from pathlib import Path
from . import config
from .state import AppState

class AudioService:
    """
    音频服务类：负责管理音频发送队列，并通过 TCP 协议将 WAV 数据流推送到 ESP32。
    使用单一消费者线程 (_worker) 串行处理音频发送，避免冲突。
    """
    def __init__(self, state: AppState):
        self.state = state
        self.queue = queue.Queue(maxsize=3) # 增加队列深度以缓冲对话
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def enqueue_alert(self, level: int):
        """
        将指定等级的警报音频加入发送队列。
        如果队列已满，会丢弃旧任务以优先发送最新警报。
        """
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
        self.queue.put_nowait(("FILE", config.AUDIO_MAP[level]))

    def play_pcm_bytes(self, pcm_data: bytes, sample_rate=16000):
        """
        播放一段原始 PCM 数据 (用于 TTS 回复)
        """
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
        self.queue.put_nowait(("RAW", pcm_data, sample_rate))

    def _worker(self):
        """后台线程，持续监听队列并处理发送任务"""
        while True:
            item = self.queue.get()
            ok = False
            
            if item[0] == "FILE":
                wav_path = item[1]
                ok = self._send_wav_file(wav_path)
            elif item[0] == "RAW":
                _, data, sr = item
                ok = self._send_raw_pcm(data, sr)
                
            self.state.update_audio_status(ok, time.time())
            self.queue.task_done()

    def _send_wav_file(self, wav_path: Path) -> bool:
        """
        读取 WAV 文件并按照自定义协议推送到 ESP32。
        
        协议格式 (PCM1 Header):
        - Magic: "PCM1" (4 bytes)
        - SampleRate: uint32
        - Channels: uint16 (必须为 1)
        - BitsPerSample: uint16 (必须为 16)
        - DataLength: uint32
        - Body: PCM Raw Data
        """
        try:
            if not wav_path.exists(): return False
            with wave.open(str(wav_path), "rb") as wf:
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                    return False
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())

            return self._send_raw_pcm(pcm, sr)
        except Exception as e:
            print(f"WAV Error: {e}")
            return False

    def _send_raw_pcm(self, pcm_data: bytes, sample_rate: int) -> bool:
        """
        底层发送逻辑，包含重试机制
        """
        # PCM1 Header
        header = (b"PCM1" + int(sample_rate).to_bytes(4, "little") + (1).to_bytes(2, "little") + 
                  (16).to_bytes(2, "little") + len(pcm_data).to_bytes(4, "little"))

        # 重试机制：最多尝试 3 次
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # 建立 TCP 连接 (2秒超时)
                with socket.create_connection((config.ESP32_IP, config.TTS_TCP_PORT), timeout=2.0) as s:
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.sendall(header)
                    chunk = 4096 
                    for i in range(0, len(pcm_data), chunk):
                        s.sendall(pcm_data[i:i + chunk])
                return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    # 指数退避：0.2s, 0.4s
                    time.sleep(0.2 * (attempt + 1))
                    continue
                print(f"[Audio] 发送失败 (尝试 {max_attempts} 次): {e}")
                return False
        return False

    # =========================
    # 寻物模式: 盖格计数器哔哔声
    # =========================
    def generate_beep(self, duration_ms: int = None, freq: int = None) -> bytes:
        """
        生成指定频率和时长的哔哔声 PCM 数据
        
        Args:
            duration_ms: 哔哔声时长 (毫秒)
            freq: 频率 (Hz)
            
        Returns:
            16-bit PCM 数据 (bytes)
        """
        duration_ms = duration_ms or config.BEEP_DURATION_MS
        freq = freq or config.BEEP_FREQ
        sample_rate = config.BEEP_SAMPLE_RATE
        
        # 计算采样点数
        num_samples = int(sample_rate * duration_ms / 1000)
        
        # 生成正弦波
        t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)
        wave_data = np.sin(2 * np.pi * freq * t)
        
        # 应用淡入淡出以避免爆音
        fade_samples = min(50, num_samples // 4)
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        wave_data[:fade_samples] *= fade_in
        wave_data[-fade_samples:] *= fade_out
        
        # 转换为 16-bit PCM
        pcm_data = (wave_data * 32767 * 0.5).astype(np.int16)  # 0.5 降低音量避免刺耳
        return pcm_data.tobytes()

    def play_geiger_beep(self):
        """
        播放一次盖格计数器哔哔声（用于寻物模式）
        该方法是非阻塞的，会将哔哔声加入队列
        """
        beep_pcm = self.generate_beep()
        # 直接发送，不经过队列以避免延迟
        try:
            self._send_raw_pcm(beep_pcm, config.BEEP_SAMPLE_RATE)
        except Exception as e:
            print(f"[Geiger] 哔哔声发送失败: {e}")
