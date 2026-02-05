import threading
import time
import numpy as np
from typing import List, Dict, Any, Optional

class AppState:
    """
    应用程序的全局状态管理类。
    使用线程锁 (threading.Lock) 确保多线程环境下的数据安全。
    """
    def __init__(self):
        self.lock = threading.Lock()
        
        # =========================
        # 相机与帧数据 (Camera & Frames)
        # =========================
        # 使用 Condition 变量实现视频流的事件驱动 (Event-driven Video Streaming)
        self.frame_condition = threading.Condition(self.lock)
        
        self.latest_frame_jpg: Optional[bytes] = None # 用于 Web 推流的 JPEG 数据
        self.latest_raw_frame: Optional[np.ndarray] = None # 用于推理的原始 NumPy 数组
        self.latest_raw_ts = 0.0 # 原始帧的时间戳
        self.latest_ts = 0.0     # 处理完成的时间戳
        self.latest_shape = (0, 0) # 帧分辨率 (H, W)

        # =========================
        # 检测结果 (Detection Results)
        # =========================
        self.latest_boxes: List[Dict[str, Any]] = [] # 检测到的边界框列表
        self.latest_count = 0        # 目标数量
        self.latest_infer_ms = 0.0   # 推理耗时 (ms)
        self.latest_delay_ms = 0.0   # 整体延迟 (ms)
        self.latest_fps_infer = 0.0  # 推理 FPS

        # =========================
        # 警报状态 (Alert State)
        # =========================
        self.latest_alert_level = 0  # 当前帧的瞬时警报等级
        self.latest_alert_text = ""  # 警报文本
        self.latest_alert_target: Optional[Dict[str, Any]] = None # 主要风险目标
        self.latest_should_notify = False # 是否应该由 UI 显示强提醒
        
        # =========================
        # 音频发送状态 (Audio Sending)
        # =========================
        self.last_send_ts = 0.0 # 最近一次音频发送时间
        self.last_send_ok = False # 最近一次发送是否成功
        
        # =========================
        # 内部历史状态 (Internal History)
        # =========================
        self.prev_max_area_ratio: Dict[str, float] = {} # 上一帧各目标的面积占比，用于计算增长率
        self.last_alert_time = {1: 0.0, 2: 0.0, 3: 0.0} # 各等级警报上次触发时间 (CoolDown)
        self.last_alert_emit_ts = 0.0 # 全局最后一次警报发出的时间
        
        # =========================
        # 稳定性滤波器 (Stability Filters)
        # =========================
        self.alert_on_count = 0  # 连续触发计数 (防抖动)
        self.alert_off_count = 0 # 连续未触发计数
        self.stable_alert_level = 0 # 稳定后的输出警报等级
        self.stable_alert_text = ""
        self.stable_alert_target: Optional[Dict[str, Any]] = None

        # =========================
        # 语音助手状态 (Voice Assistant State)
        # =========================
        self.latest_voice_status = "idle" # idle, listening, processing, speaking
        self.latest_voice_log: List[Dict[str, str]] = [] # [{"role": "user", "content": "..."}]

        # =========================
        # 寻物模式状态 (Search Mode State)
        # =========================
        self.search_mode = False           # 是否处于寻物模式
        self.search_target_class = ""      # 目标类别 (COCO 类名)
        self.search_target_label = ""      # 用户输入的原始标签
        self.search_last_beep_ts = 0.0     # 上次哔哔声时间
        self.search_target_info: Optional[Dict[str, Any]] = None  # 目标位置信息

    def update_frame(self, frame: np.ndarray, ts: float):
        """更新最新的相机帧数据"""
        with self.lock:
            self.latest_raw_frame = frame
            self.latest_raw_ts = ts
            self.latest_shape = frame.shape[:2]

    def get_frame(self):
        """获取当前最新的帧及其时间戳"""
        with self.lock:
            return self.latest_raw_frame, self.latest_raw_ts

    def heartbeat(self):
        """纯心跳更新，用于在无相机帧时告知前端服务仍在线"""
        with self.lock:
            self.latest_ts = time.time()

    def update_detection(self, 
                       boxes: List[Dict[str, Any]], 
                       infer_ms: float, 
                       fps: float, 
                       delay: float, 
                       jpg: bytes):
        """更新推理结果和 HUD 画面"""
        with self.lock:
            self.latest_ts = time.time()
            self.latest_boxes = boxes
            self.latest_count = len(boxes)
            self.latest_infer_ms = infer_ms
            self.latest_fps_infer = fps
            self.latest_delay_ms = delay
            self.latest_frame_jpg = jpg
            self.frame_condition.notify_all()

    def update_alert(self, level: int, text: str, target: Optional[Dict[str, Any]], should_notify: bool):
        """更新经过去抖动处理后的稳定警报状态"""
        with self.lock:
            self.latest_alert_level = level
            self.latest_alert_text = text
            self.latest_alert_target = target
            self.latest_should_notify = should_notify

    def update_audio_status(self, ok: bool, ts: float):
        """更新音频发送的健康状态"""
        with self.lock:
            self.last_send_ok = ok
            if ok:
                self.last_send_ts = ts

    def update_voice_state(self, status: Optional[str] = None):
        """更新语音助手状态"""
        with self.lock:
            if status:
                self.latest_voice_status = status

    def add_voice_log(self, role: str, content: str):
        """添加一条语音交互记录"""
        with self.lock:
            # 只保留最近 10 条记录
            if len(self.latest_voice_log) >= 10:
                self.latest_voice_log.pop(0)
            self.latest_voice_log.append({
                "role": role,
                "content": content,
                "ts": time.time()
            })

    # =========================
    # 寻物模式控制方法
    # =========================
    def start_search(self, target_class: str, label: str):
        """进入寻物模式"""
        with self.lock:
            self.search_mode = True
            self.search_target_class = target_class
            self.search_target_label = label
            self.search_last_beep_ts = 0.0
            self.search_target_info = None
            print(f"[SearchMode] 开始寻找: {label} -> {target_class}")

    def stop_search(self):
        """退出寻物模式"""
        with self.lock:
            self.search_mode = False
            self.search_target_class = ""
            self.search_target_label = ""
            self.search_target_info = None
            print("[SearchMode] 寻物模式已关闭")

    def update_search_target(self, info: Optional[Dict[str, Any]]):
        """更新目标位置信息"""
        with self.lock:
            self.search_target_info = info

    def get_search_state(self) -> Dict[str, Any]:
        """获取寻物模式状态"""
        with self.lock:
            return {
                "active": self.search_mode,
                "target_class": self.search_target_class,
                "target_label": self.search_target_label,
                "target_info": self.search_target_info
            }

    def get_ui_data(self) -> Dict[str, Any]:
        """打包前端 UI 所需的所有状态数据"""
        with self.lock:
            return {
                "ts": self.latest_ts,
                "shape": {"h": self.latest_shape[0], "w": self.latest_shape[1]},
                "count": self.latest_count,
                "infer_ms": self.latest_infer_ms,
                "fps_infer": self.latest_fps_infer,
                "delay_ms": self.latest_delay_ms,
                "alert_level": self.latest_alert_level,
                "alert_text": self.latest_alert_text,
                "alert_target": self.latest_alert_target,
                "should_notify": self.latest_should_notify,
                "last_send_ts": self.last_send_ts,
                "last_send_ok": self.last_send_ok,
                # Voice Data
                "voice_status": self.latest_voice_status,
                "voice_log": self.latest_voice_log,
                # Search Mode Data
                "search_mode": self.search_mode,
                "search_target": self.search_target_label,
                "search_info": self.search_target_info
            }
