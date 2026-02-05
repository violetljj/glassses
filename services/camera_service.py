import time
import threading
import requests
import numpy as np
import cv2
from typing import Optional
from . import config
from .state import AppState

class CameraService:
    """
    相机服务类：通过 MJPEG 流持续获取视频帧。
    相比 HTTP 轮询，MJPEG 流显著降低延迟并提高帧率。
    """
    def __init__(self, state: AppState):
        self.state = state
        self._fail_count = 0
        self._last_error = None
        self._running = True
        # 构建 MJPEG 流 URL (ESP32 固件的流端口是 81)
        self._stream_url = f"http://{config.ESP32_IP}:81/stream"
        self.thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.thread.start()

    def _stream_loop(self) -> None:
        """
        MJPEG 流读取循环。
        持续连接 ESP32 的 /stream 端点，解析 multipart 边界提取 JPEG 帧。
        """
        print(f"[Camera] 启动 MJPEG 流模式: {self._stream_url}")
        backoff = config.CAPTURE_BACKOFF_BASE

        while self._running:
            try:
                # 使用流式响应，保持长连接
                response = requests.get(
                    self._stream_url,
                    stream=True,
                    timeout=(3.0, 10.0)  # (连接超时, 读取超时)
                )
                
                if response.status_code != 200:
                    self._last_error = f"HTTP {response.status_code}"
                    raise Exception(self._last_error)

                # 连接成功
                if self._fail_count > 0:
                    print(f"[Camera] MJPEG 流连接成功 (之前失败 {self._fail_count} 次)")
                self._fail_count = 0
                backoff = config.CAPTURE_BACKOFF_BASE

                # 解析 MJPEG 流
                self._parse_mjpeg_stream(response)

            except requests.exceptions.Timeout:
                self._last_error = "连接超时"
            except requests.exceptions.ConnectionError:
                self._last_error = "连接被拒绝"
            except Exception as e:
                self._last_error = str(e)

            # 连接断开或出错，重试
            self._fail_count += 1
            if self._fail_count % config.CAPTURE_FAIL_LOG_EVERY == 1:
                print(f"[Camera] MJPEG 流断开 ({self._fail_count}次): {self._last_error}")
            
            time.sleep(backoff)
            backoff = min(config.CAPTURE_BACKOFF_MAX, backoff * 1.5)

    def _parse_mjpeg_stream(self, response) -> None:
        """
        解析 MJPEG multipart 流，提取每一帧 JPEG 图像。
        MJPEG 格式: --boundary\r\nContent-Type: image/jpeg\r\n\r\n<JPEG数据>\r\n
        """
        buffer = b''
        frame_count = 0
        last_frame_time = time.time()

        for chunk in response.iter_content(chunk_size=4096):
            if not self._running:
                break
            
            buffer += chunk

            # 查找 JPEG 帧的起始和结束标记
            while True:
                # JPEG 起始标记: FFD8
                start = buffer.find(b'\xff\xd8')
                if start == -1:
                    # 清理无用数据，保留最后 2 字节（防止截断）
                    if len(buffer) > 2:
                        buffer = buffer[-2:]
                    break

                # JPEG 结束标记: FFD9
                end = buffer.find(b'\xff\xd9', start + 2)
                if end == -1:
                    # 帧不完整，等待更多数据
                    break

                # 提取完整的 JPEG 帧
                jpg_data = buffer[start:end + 2]
                buffer = buffer[end + 2:]

                # 解码并更新状态
                frame = self._decode_frame(jpg_data)
                if frame is not None:
                    self.state.update_frame(frame, time.time())
                    frame_count += 1

                    # 每 100 帧打印一次性能日志
                    if frame_count % 100 == 0:
                        elapsed = time.time() - last_frame_time
                        fps = 100 / elapsed if elapsed > 0 else 0
                        print(f"[Camera] MJPEG 帧率: {fps:.1f} FPS")
                        last_frame_time = time.time()

    def _decode_frame(self, jpg_data: bytes) -> Optional[np.ndarray]:
        """解码 JPEG 数据为 OpenCV 图像"""
        try:
            arr = np.frombuffer(jpg_data, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None

    def stop(self) -> None:
        """停止相机服务"""
        self._running = False
