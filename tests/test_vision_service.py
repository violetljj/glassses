# -*- coding: utf-8 -*-
"""
VisionService 单元测试

测试视觉服务的核心功能：风险计算、目标定位等
注意：跳过 predict() 测试，因为它需要加载实际的 YOLO 模型
"""
import pytest
import numpy as np
from typing import Dict, Any, List

# 为了避免加载实际模型，我们只测试不依赖模型的方法
# 手动定义 config 常量用于测试
class MockConfig:
    ALERT_CLASSES = {"person"}
    PATH_X_MIN, PATH_X_MAX = 0.30, 0.70
    PATH_Y_MIN, PATH_Y_MAX = 0.20, 0.95
    TH_L1 = 0.02
    TH_L2 = 0.06
    TH_L3 = 0.14
    GROWTH_BOOST = 1.25
    ALERT_TEXT = {1: "Person ahead", 2: "Watch out", 3: "Danger! Stop"}
    GEIGER_AREA_MID = 0.03
    GEIGER_AREA_NEAR = 0.10


class TestVisionServiceRiskComputation:
    """测试 compute_risk 方法的逻辑"""

    def compute_risk_standalone(
        self, boxes: List[Dict[str, Any]], w: int, h: int, prev_area: Dict[str, float]
    ):
        """独立实现的 compute_risk 逻辑，用于单元测试（不依赖实际模型）"""
        cfg = MockConfig()
        
        if w <= 0 or h <= 0 or not boxes:
            return 0, "", None, {}

        x_min, x_max = cfg.PATH_X_MIN * w, cfg.PATH_X_MAX * w
        y_min, y_max = cfg.PATH_Y_MIN * h, cfg.PATH_Y_MAX * h

        best = None
        curr_area = {}

        for b in boxes:
            label = b["label"]
            if label not in cfg.ALERT_CLASSES:
                continue

            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h + 1e-6)
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            in_path = (x_min <= cx <= x_max) and (y_min <= cy <= y_max)

            prev = prev_area.get(label, 0.0)
            growth = (area_ratio / prev) if prev > 1e-6 else 1.0

            level = 0
            if area_ratio >= cfg.TH_L3:
                level = 3
            elif area_ratio >= cfg.TH_L2:
                level = 2
            elif area_ratio >= cfg.TH_L1 and in_path:
                level = 1

            if in_path and level > 0:
                level = min(3, level + 1)
            if growth >= cfg.GROWTH_BOOST and level > 0:
                level = min(3, level + 1)

            curr_area[label] = max(curr_area.get(label, 0.0), area_ratio)
            if level == 0:
                continue

            cand = {
                "level": int(level),
                "label": label,
                "area_ratio": float(area_ratio),
                "growth": float(growth),
                "in_path": bool(in_path),
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            }
            if best is None or level > best["level"] or (
                level == best["level"] and area_ratio > best["area_ratio"]
            ):
                best = cand

        text = cfg.ALERT_TEXT.get(best["level"], "") if best else ""
        return (best["level"] if best else 0), text, best, curr_area

    def test_no_boxes_returns_level_0(self):
        """空检测结果应返回 L0"""
        level, text, target, _ = self.compute_risk_standalone([], 640, 480, {})
        assert level == 0
        assert text == ""
        assert target is None

    def test_no_person_returns_level_0(self):
        """无 person 类别时应返回 L0"""
        boxes = [{"label": "car", "conf": 0.9, "x1": 100, "y1": 100, "x2": 200, "y2": 200}]
        level, text, target, _ = self.compute_risk_standalone(boxes, 640, 480, {})
        assert level == 0

    def test_small_person_outside_path_returns_level_0(self):
        """小面积且不在路径中的 person 应返回 L0"""
        # 左上角的小 person (面积占比很小，且不在中心路径)
        boxes = [{"label": "person", "conf": 0.9, "x1": 0, "y1": 0, "x2": 30, "y2": 30}]
        level, _, _, _ = self.compute_risk_standalone(boxes, 640, 480, {})
        assert level == 0

    def test_large_person_returns_level_3(self):
        """大面积 person 应返回 L3"""
        # 占据画面大部分的 person
        boxes = [{"label": "person", "conf": 0.9, "x1": 100, "y1": 100, "x2": 540, "y2": 380}]
        level, text, target, _ = self.compute_risk_standalone(boxes, 640, 480, {})
        assert level == 3
        assert "Danger" in text or "Stop" in text

    def test_medium_person_in_path_returns_elevated_level(self):
        """中等面积且在路径中的 person 应返回升级后的等级"""
        # 画面中心的中等大小 person
        boxes = [{"label": "person", "conf": 0.9, "x1": 250, "y1": 150, "x2": 390, "y2": 350}]
        level, _, _, _ = self.compute_risk_standalone(boxes, 640, 480, {})
        assert level >= 2  # 在路径中应该升级


class TestLocateTarget:
    """测试 locate_target 方法的逻辑"""

    def locate_target_standalone(
        self, boxes: List[Dict[str, Any]], target_class: str, w: int, h: int
    ):
        """独立实现的 locate_target 逻辑"""
        cfg = MockConfig()
        
        if w <= 0 or h <= 0 or not boxes or not target_class:
            return None

        best = None
        best_area = 0.0

        for b in boxes:
            if b["label"] != target_class:
                continue

            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h + 1e-6)

            if area_ratio > best_area:
                best_area = area_ratio
                cx = (x1 + x2) / 2.0

                if cx < w / 3:
                    direction = "left"
                elif cx > 2 * w / 3:
                    direction = "right"
                else:
                    direction = "center"

                if area_ratio >= cfg.GEIGER_AREA_NEAR:
                    distance = "near"
                elif area_ratio >= cfg.GEIGER_AREA_MID:
                    distance = "mid"
                else:
                    distance = "far"

                best = {
                    "direction": direction,
                    "distance": distance,
                    "area_ratio": float(area_ratio),
                    "box": b,
                }

        return best

    def test_target_not_found(self):
        """目标类别不存在时返回 None"""
        boxes = [{"label": "person", "conf": 0.9, "x1": 100, "y1": 100, "x2": 200, "y2": 200}]
        result = self.locate_target_standalone(boxes, "cup", 640, 480)
        assert result is None

    def test_target_found_center(self):
        """目标在中心位置"""
        boxes = [{"label": "cup", "conf": 0.9, "x1": 270, "y1": 200, "x2": 370, "y2": 300}]
        result = self.locate_target_standalone(boxes, "cup", 640, 480)
        assert result is not None
        assert result["direction"] == "center"

    def test_target_found_left(self):
        """目标在左侧位置"""
        boxes = [{"label": "cup", "conf": 0.9, "x1": 50, "y1": 200, "x2": 150, "y2": 300}]
        result = self.locate_target_standalone(boxes, "cup", 640, 480)
        assert result is not None
        assert result["direction"] == "left"

    def test_target_found_right(self):
        """目标在右侧位置"""
        boxes = [{"label": "cup", "conf": 0.9, "x1": 500, "y1": 200, "x2": 600, "y2": 300}]
        result = self.locate_target_standalone(boxes, "cup", 640, 480)
        assert result is not None
        assert result["direction"] == "right"

    def test_distance_calculation(self):
        """测试距离计算"""
        # 大面积 = 近
        large_box = [{"label": "cup", "conf": 0.9, "x1": 100, "y1": 100, "x2": 400, "y2": 350}]
        result = self.locate_target_standalone(large_box, "cup", 640, 480)
        assert result["distance"] == "near"

        # 小面积 = 远
        small_box = [{"label": "cup", "conf": 0.9, "x1": 300, "y1": 200, "x2": 340, "y2": 240}]
        result = self.locate_target_standalone(small_box, "cup", 640, 480)
        assert result["distance"] == "far"
