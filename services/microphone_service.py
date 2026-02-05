import socket
import threading
import time
import wave
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List

class MicrophoneService:
    """
    麦克风服务：监听 TCP 端口接收来自 ESP32 的音频数据。
    支持两种模式：
    - 传统模式：本地 VAD + 保存 WAV 文件
    - Omni 模式：直接推送 PCM 到 OmniService（Omni 内置 VAD）
    """
    def __init__(self, callback: Optional[Callable[[Path], None]] = None, port: int = 23457, save_dir: str = "recordings"):
        self.port = port
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.callback = callback  # 传统模式：录音完成后的回调
        self.omni_service = None  # Omni 模式：直接推送音频
        self.running = True
        
        # 启动监听线程
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()
        print(f"Directory for recordings: {self.save_dir.absolute()}")

    def set_callback(self, callback: Callable[[Path], None]) -> None:
        """设置传统模式回调"""
        self.callback = callback
    
    def set_omni_service(self, omni_service) -> None:
        """设置 Omni 模式：直接推送音频"""
        self.omni_service = omni_service
        print("[MIC] Omni mode enabled - audio will be pushed directly to OmniService")

    def _server_loop(self) -> None:
        """TCP 服务器主循环"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server.bind(("0.0.0.0", self.port))
            server.listen(1)
            print(f"Microphone Service listening on port {self.port}")
            
            while self.running:
                client, addr = server.accept()
                # 根据模式选择处理方式
                if self.omni_service:
                    self._handle_omni_stream(client)
                else:
                    self._handle_client_stream(client)
                
        except Exception as e:
            print(f"Microphone Service Error: {e}")
        finally:
            server.close()

    def _handle_omni_stream(self, client) -> None:
        """
        Omni 模式：直接将音频推送到 OmniService
        Omni 内置 VAD，无需本地处理
        """
        CHUNK = 3200  # 100ms @ 16kHz
        
        client.settimeout(None)
        addr = client.getpeername()
        print(f"[MIC] ✅ Client connected from {addr} (Omni mode)")
        
        try:
            while self.running:
                data = client.recv(CHUNK)
                if not data:
                    break
                
                # 直接推送到 Omni
                if self.omni_service and self.omni_service.connected:
                    self.omni_service.append_audio(data)
                    
        except Exception as e:
            print(f"[MIC] Stream error: {e}")
        finally:
            client.close()
            print("[MIC] Client disconnected")

    def _handle_client_stream(self, client) -> None:
        """
        传统模式：本地 VAD + 保存 WAV 文件
        """
        import audioop
        from . import config
        
        # WAV 参数
        CHANNELS = 1
        RATE = 16000
        WIDTH = 2
        CHUNK = 1024
        
        # VAD 参数 (从配置文件读取)
        THRESHOLD = getattr(config, 'VAD_THRESHOLD', 300)
        SILENCE_LIMIT = getattr(config, 'VAD_SILENCE_LIMIT', 1.0)
        DEBUG = getattr(config, 'VAD_DEBUG', False)
        
        frames = []
        silence_start = None
        is_speaking = False
        last_debug_time = 0
        first_data_received = False
        
        client.settimeout(None)
        addr = client.getpeername()
        print(f"[MIC] ✅ Client connected from {addr}, starting VAD (threshold={THRESHOLD})")
        
        try:
            while self.running:
                data = client.recv(CHUNK)
                if not data: break
                
                if not first_data_received:
                    print(f"[MIC] 🎤 First audio chunk received: {len(data)} bytes")
                    first_data_received = True
                
                rms = audioop.rms(data, WIDTH)
                
                now = time.time()
                if DEBUG and now - last_debug_time >= 1.0:
                    status = "SPEAKING" if is_speaking else "SILENT"
                    print(f"[VAD] RMS: {rms:5d} | Threshold: {THRESHOLD} | Status: {status}")
                    last_debug_time = now
                
                if rms > THRESHOLD:
                    is_speaking = True
                    silence_start = None
                else:
                    if is_speaking:
                        if silence_start is None:
                            silence_start = time.time()
                        elif (time.time() - silence_start) > SILENCE_LIMIT:
                            self._save_and_notify(frames, CHANNELS, WIDTH, RATE)
                            frames = []
                            is_speaking = False
                            silence_start = None
                            
                if is_speaking or (frames and len(frames) < RATE * 10):
                    frames.append(data)
                    
        except Exception as e:
            pass
        finally:
            client.close()
            if frames and len(frames) > RATE * 0.5:
                self._save_and_notify(frames, CHANNELS, WIDTH, RATE)

    def _save_and_notify(self, frames: List[bytes], channels: int, width: int, rate: int) -> None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.save_dir / f"cmd_{timestamp}.wav"
        
        try:
            with wave.open(str(filename), 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(width)
                wf.setframerate(rate)
                wf.writeframes(b''.join(frames))
            
            print(f"Voice Command Saved: {filename.name}")
            if self.callback:
                self.callback(filename)
        except Exception as e:
            print(f"Save Error: {e}")

if __name__ == "__main__":
    svc = MicrophoneService()
    while True:
        time.sleep(1)

