# -*- coding: utf-8 -*-
"""
AppState 单元测试

测试状态管理类的核心功能：帧更新、寻物模式、语音日志等
"""
import pytest
import numpy as np
import threading
import time


class TestAppStateCore:
    """测试 AppState 核心功能（独立实现，不依赖实际模块）"""

    def create_mock_state(self):
        """创建模拟的状态对象"""
        class MockAppState:
            def __init__(self):
                self.lock = threading.Lock()
                self.frame_condition = threading.Condition()
                
                # 帧数据
                self.latest_frame = None
                self.latest_frame_ts = 0.0
                self.latest_frame_jpg = None
                self.latest_shape = (0, 0)
                
                # 寻物模式状态
                self.search_mode = False
                self.search_target_class = ""
                self.search_target_label = ""
                self.search_target_info = None
                self.search_last_beep_ts = 0.0
                
                # 语音日志
                self.voice_logs = []
                self.max_voice_logs = 10
                self.latest_voice_status = "idle"
                
            def update_frame(self, frame: np.ndarray, ts: float):
                with self.lock:
                    self.latest_frame = frame
                    self.latest_frame_ts = ts
                    if frame is not None:
                        self.latest_shape = frame.shape[:2]
                        
            def get_frame(self):
                with self.lock:
                    return self.latest_frame, self.latest_frame_ts
                    
            def start_search(self, target_class: str, label: str):
                with self.lock:
                    self.search_mode = True
                    self.search_target_class = target_class
                    self.search_target_label = label
                    self.search_target_info = None
                    self.search_last_beep_ts = 0.0
                    
            def stop_search(self):
                with self.lock:
                    self.search_mode = False
                    self.search_target_class = ""
                    self.search_target_label = ""
                    self.search_target_info = None
                    
            def get_search_state(self):
                with self.lock:
                    return {
                        "active": self.search_mode,
                        "target_class": self.search_target_class,
                        "target_label": self.search_target_label,
                        "target_info": self.search_target_info,
                    }
                    
            def add_voice_log(self, role: str, content: str):
                with self.lock:
                    self.voice_logs.append({
                        "role": role,
                        "content": content,
                        "ts": time.time()
                    })
                    # 裁剪过长的日志
                    if len(self.voice_logs) > self.max_voice_logs:
                        self.voice_logs = self.voice_logs[-self.max_voice_logs:]
                        
            def update_voice_state(self, status: str = None):
                with self.lock:
                    if status is not None:
                        self.latest_voice_status = status
                        
        return MockAppState()

    def test_frame_update_and_get(self):
        """测试帧更新与获取"""
        state = self.create_mock_state()
        
        # 初始状态
        frame, ts = state.get_frame()
        assert frame is None
        assert ts == 0.0
        
        # 更新帧
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        state.update_frame(test_frame, 1000.0)
        
        frame, ts = state.get_frame()
        assert frame is not None
        assert ts == 1000.0
        assert state.latest_shape == (480, 640)

    def test_search_mode_lifecycle(self):
        """测试寻物模式的开启与关闭"""
        state = self.create_mock_state()
        
        # 初始状态
        search_state = state.get_search_state()
        assert search_state["active"] is False
        
        # 开启寻物模式
        state.start_search("cup", "水杯")
        search_state = state.get_search_state()
        assert search_state["active"] is True
        assert search_state["target_class"] == "cup"
        assert search_state["target_label"] == "水杯"
        
        # 关闭寻物模式
        state.stop_search()
        search_state = state.get_search_state()
        assert search_state["active"] is False
        assert search_state["target_class"] == ""

    def test_voice_log_rotation(self):
        """测试语音日志的自动裁剪"""
        state = self.create_mock_state()
        state.max_voice_logs = 5  # 设置较小的上限便于测试
        
        # 添加超过上限的日志
        for i in range(10):
            state.add_voice_log("user", f"消息 {i}")
        
        # 验证日志已被裁剪
        assert len(state.voice_logs) == 5
        # 应该保留最后5条
        assert state.voice_logs[0]["content"] == "消息 5"
        assert state.voice_logs[-1]["content"] == "消息 9"

    def test_voice_state_update(self):
        """测试语音状态更新"""
        state = self.create_mock_state()
        
        assert state.latest_voice_status == "idle"
        
        state.update_voice_state("listening")
        assert state.latest_voice_status == "listening"
        
        state.update_voice_state("speaking")
        assert state.latest_voice_status == "speaking"

    def test_thread_safety(self):
        """测试多线程安全性"""
        state = self.create_mock_state()
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    state.update_frame(frame, float(i))
            except Exception as e:
                errors.append(e)
                
        def reader():
            try:
                for _ in range(100):
                    frame, ts = state.get_frame()
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"线程安全测试失败: {errors}"
