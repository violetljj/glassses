import time
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from ultralytics import YOLO
from . import config

class VisionService:
    """
    视觉服务类：负责加载模型、执行推理、计算风险等级以及绘制 HUD。
    """
    def __init__(self):
        # 加载 YOLO 模型
        self.model = YOLO(config.MODEL_PATH)
        
        # 检测 CUDA 可用性
        import torch
        self.use_cuda = torch.cuda.is_available()
        self.use_half = self.use_cuda and getattr(config, 'USE_HALF_PRECISION', False)
        if self.use_half:
            print("CUDA detected, FP16 half precision will be used for inference.")
        
        # 模型预热 (Warmup)：先跑一次空数据，避免第一次推理延迟过高
        dummy = np.zeros((config.IMG_SIZE, config.IMG_SIZE, 3), dtype=np.uint8)
        self.model.predict(dummy, imgsz=config.IMG_SIZE, verbose=False, half=self.use_half)

    def predict(self, frame: np.ndarray) -> Tuple[List[Dict[str, Any]], Any]:
        """
        对输入帧执行 YOLO 推理。
        
        Args:
            frame: 原始图像数据 (NumPy array)
            
        Returns:
            boxes: 检测到的目标列表，包含坐标、置信度和标签
            r: YOLO 的原始结果对象 (Result)
            infer_ms: 推理耗时 (毫秒)
        """
        t0 = time.time()
        results = self.model.predict(
            frame, 
            imgsz=config.IMG_SIZE, 
            conf=config.CONF_THRESHOLD, 
            iou=config.IOU_THRESHOLD,
            verbose=False,
            half=self.use_half
        )
        infer_ms = (time.time() - t0) * 1000.0
        
        r = results[0]
        boxes = []
        if r.boxes is not None:
            xyxy = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            clss = r.boxes.cls.cpu().numpy().astype(int)
            names = self.model.names
            for (x1, y1, x2, y2), c, k in zip(xyxy, confs, clss):
                boxes.append({
                    "label": names.get(int(k), str(int(k))),
                    "conf": float(c),
                    "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
                })
        return boxes, r, infer_ms

    def compute_risk(self, boxes: List[Dict[str, Any]], w: int, h: int, prev_area: Dict[str, float]) -> Tuple[int, str, Optional[Dict[str, Any]], Dict[str, float]]:
        """
        计算当前帧的风险评估等级 (L0 - L3)。
        
        逻辑说明：
        1. 过滤不在关注列表 (ALERT_CLASSES) 中的目标。
        2. 计算目标面积占比 (area_ratio) 和中心点位置。
        3. 判断目标是否位于行走路径 (in_path) 内。
        4. 对比上一帧，计算目标的面积增长率 (growth)。
        5. 根据面积、位置和增长率综合评定风险等级。
        
        Returns:
            (level, text, best_target, curr_area)
        """
        if w <= 0 or h <= 0 or not boxes:
            return 0, "", None, {}

        # 定义行走路径区域的像素坐标
        x_min, x_max = config.PATH_X_MIN * w, config.PATH_X_MAX * w
        y_min, y_max = config.PATH_Y_MIN * h, config.PATH_Y_MAX * h
        
        best = None
        curr_area = {}

        for b in boxes:
            label = b["label"]
            if label not in config.ALERT_CLASSES:
                continue

            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            # 计算面积占比
            area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h + 1e-6)
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            # 判断是否在中心路径
            in_path = (x_min <= cx <= x_max) and (y_min <= cy <= y_max)

            # 计算增长率
            prev = prev_area.get(label, 0.0)
            growth = (area_ratio / prev) if prev > 1e-6 else 1.0

            # 基础等级判定
            level = 0
            if area_ratio >= config.TH_L3: level = 3
            elif area_ratio >= config.TH_L2: level = 2
            elif area_ratio >= config.TH_L1 and in_path: level = 1

            # 风险升级逻辑
            if in_path and level > 0: level = min(3, level + 1)
            if growth >= config.GROWTH_BOOST and level > 0: level = min(3, level + 1)

            curr_area[label] = max(curr_area.get(label, 0.0), area_ratio)
            if level == 0: continue

            cand = {
                "level": int(level), "label": label, "area_ratio": float(area_ratio),
                "growth": float(growth), "in_path": bool(in_path),
                "x1": x1, "y1": y1, "x2": x2, "y2": y2
            }
            # 保留风险最高或面积最大的目标作为主要目标
            if best is None or level > best["level"] or (level == best["level"] and area_ratio > best["area_ratio"]):
                best = cand

        text = config.ALERT_TEXT.get(best["level"], "") if best else ""
        return (best["level"] if best else 0), text, best, curr_area

    def draw_hud(self, annotated: np.ndarray, fps: float, delay: float, count: int, level: int, text: str) -> bytes:
        """
        在图像上绘制 HUD 信息 (FPS, 延迟, 警报) 并编码为 JPEG。
        """
        cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated, f"Delay: {delay:.0f} ms", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated, f"Count: {count}", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if level > 0:
            cv2.putText(annotated, f"ALERT L{level}", (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)
            # 注意: OpenCV 默认不支持中文，中文警报文本在前端显示
        
        ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), config.JPEG_QUALITY])
        return buf.tobytes() if ok else b""

    def locate_target(self, boxes: List[Dict[str, Any]], target_class: str, w: int, h: int) -> Optional[Dict[str, Any]]:
        """
        在检测结果中定位特定目标，返回位置信息（用于寻物模式）。
        
        Args:
            boxes: 检测到的边界框列表
            target_class: 目标类别 (COCO 类名)
            w, h: 图像宽高
            
        Returns:
            位置信息字典，包含 direction, distance, area_ratio, box
            如果未找到目标，返回 None
        """
        if w <= 0 or h <= 0 or not boxes or not target_class:
            return None
        
        best = None
        best_area = 0.0
        
        for b in boxes:
            if b["label"] != target_class:
                continue
            
            x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
            area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h + 1e-6)
            
            # 选择面积最大的目标（通常是最近的）
            if area_ratio > best_area:
                best_area = area_ratio
                cx = (x1 + x2) / 2.0
                
                # 计算方向 (将画面分为左/中/右三等分)
                if cx < w / 3:
                    direction = "left"
                elif cx > 2 * w / 3:
                    direction = "right"
                else:
                    direction = "center"
                
                # 计算距离 (根据面积占比判断)
                if area_ratio >= config.GEIGER_AREA_NEAR:
                    distance = "near"
                elif area_ratio >= config.GEIGER_AREA_MID:
                    distance = "mid"
                else:
                    distance = "far"
                
                best = {
                    "direction": direction,
                    "distance": distance,
                    "area_ratio": float(area_ratio),
                    "box": b
                }
        
        return best

