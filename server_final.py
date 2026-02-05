# -*- coding: utf-8 -*-
"""
YOLO + ESP32 Assistive Vision (FINAL+HUD)

ESP32 Camera (/capture) →
PC YOLOv8 Detection →
Risk Level Estimation →
Fixed WAV Audio →
TCP PCM Push →
ESP32 I2S Playback (MAX98357A)

Adds:
- HUD overlay (FPS/Delay/Count/Alert)
- /detect JSON endpoint
- Robust capture + error handling
"""

import time
import threading
import queue
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import socket
import wave

import cv2
import numpy as np
import requests
from flask import Flask, jsonify, Response
from flask_cors import CORS
from ultralytics import YOLO

try:
    import torch
except Exception:  # pragma: no cover - optional perf path
    torch = None

import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

# =========================
# 1) ESP32 & Network Config
# =========================
ESP32_IP = os.getenv("ESP32_IP", "192.168.132.244")
ESP32_CAPTURE_URL = f"http://{ESP32_IP}/capture"
TTS_TCP_PORT = int(os.getenv("TTS_TCP_PORT", 23456))
SERVER_PORT = int(os.getenv("SERVER_PORT", 5000))

# =========================
# 2) Fixed Audio Library
# =========================
BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"

AUDIO_MAP = {
    1: AUDIO_DIR / "l1.wav",   # 前方有人
    2: AUDIO_DIR / "l2.wav",   # 注意避让
    3: AUDIO_DIR / "l3.wav",   # 危险，请立即停下
}

# =========================
# 3) YOLO Config
# =========================
model = YOLO("yolov8n.pt")
HAS_CUDA = bool(torch and torch.cuda.is_available())
MODEL_DEVICE = 0 if HAS_CUDA else "cpu"
MODEL_HALF = bool(HAS_CUDA)
IMG_SIZE = 320
CONF = 0.35
IOU = 0.5

FETCH_INTERVAL = 0.08
INFER_INTERVAL = 0.10
CAPTURE_BACKOFF_BASE = 0.03
CAPTURE_BACKOFF_MAX = 0.5
CAPTURE_FAIL_LOG_EVERY = 30
JPEG_QUALITY = 75

# =========================
# 4) Risk Estimation Params
# =========================
PATH_X_MIN, PATH_X_MAX = 0.30, 0.70
PATH_Y_MIN, PATH_Y_MAX = 0.20, 0.95

TH_L1 = 0.02
TH_L2 = 0.06
TH_L3 = 0.14
GROWTH_BOOST = 1.25

ALERT_CLASSES = {"person"}
ALERT_COOLDOWN = {1: 2.0, 2: 1.0, 3: 0.4}
ALERT_REPEAT_MIN = {1: 5.0, 2: 3.0, 3: 2.0}
ALERT_CONSECUTIVE_ON = 3
ALERT_CONSECUTIVE_OFF = 4
last_alert_time = {1: 0.0, 2: 0.0, 3: 0.0}

ALERT_TEXT = {
    1: "Person ahead",
    2: "Watch out",
    3: "Danger! Stop",
}

# =========================
# 5) Flask & Runtime State
# =========================
app = Flask(__name__)
CORS(app)
lock = threading.Lock()
frame_cond = threading.Condition(lock)

latest_frame_jpg: Optional[bytes] = None
latest_raw_frame: Optional[np.ndarray] = None
latest_raw_ts = 0.0
latest_ts = 0.0
latest_shape = (0, 0)

latest_boxes: List[Dict[str, Any]] = []
latest_count = 0

latest_infer_ms = 0.0
latest_delay_ms = 0.0
latest_fps_infer = 0.0

latest_alert_level = 0
latest_alert_text = ""
latest_alert_target: Optional[Dict[str, Any]] = None
latest_should_notify = False
latest_last_send_ts = 0.0
latest_last_send_ok = False

prev_max_area_ratio: Dict[str, float] = {}

# Audio send queue (async)
audio_queue: "queue.Queue[Path]" = queue.Queue(maxsize=1)

alert_on_count = 0
alert_off_count = 0
stable_alert_level = 0
stable_alert_text = ""
stable_alert_target: Optional[Dict[str, Any]] = None
last_alert_emit_ts = 0.0

# =========================
# 6) Audio Sender (CORE)
# =========================
def send_wav_to_esp32(wav_path: Path) -> bool:
    """Read wav (mono, 16-bit PCM) and push as PCM1 over TCP."""
    try:
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV not found: {wav_path}")

        with wave.open(str(wav_path), "rb") as wf:
            if wf.getnchannels() != 1:
                raise ValueError("WAV must be mono (1 channel)")
            if wf.getsampwidth() != 2:
                raise ValueError("WAV must be 16-bit (sampwidth=2)")
            sr = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())

        header = (
            b"PCM1"
            + int(sr).to_bytes(4, "little")
            + (1).to_bytes(2, "little")
            + (16).to_bytes(2, "little")
            + len(pcm).to_bytes(4, "little")
        )

        with socket.create_connection((ESP32_IP, TTS_TCP_PORT), timeout=1.0) as s:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.sendall(header)

            chunk = 2048
            for i in range(0, len(pcm), chunk):
                s.sendall(pcm[i:i + chunk])
        return True
    except Exception as e:
        print(f"⚠️ Audio send failed: {repr(e)}")
        return False


# =========================
# 7) Camera Frame Fetch (robust)
# =========================
def fetch_capture_frame(session: requests.Session) -> Optional[np.ndarray]:
    """Return BGR frame or None."""
    try:
        r = session.get(ESP32_CAPTURE_URL, timeout=2.5, headers={"Connection": "close"})
        try:
            if r.status_code != 200 or len(r.content) < 1000:
                return None
            arr = np.frombuffer(r.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return None
            return frame
        finally:
            r.close()
    except Exception:
        return None


# =========================
# 8) Risk Estimation (pick best target)
# =========================
def compute_alert(
    boxes: List[Dict[str, Any]],
    w: int,
    h: int,
    prev_area: Dict[str, float],
    curr_area: Dict[str, float],
) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    """
    Return (level, text, best_target)
    best_target includes: label, area_ratio, in_path, growth, xyxy
    """
    if w <= 0 or h <= 0 or not boxes:
        return 0, "", None

    x_min = PATH_X_MIN * w
    x_max = PATH_X_MAX * w
    y_min = PATH_Y_MIN * h
    y_max = PATH_Y_MAX * h

    best: Optional[Dict[str, Any]] = None

    for b in boxes:
        label = b.get("label", "")
        if label not in ALERT_CLASSES:
            continue

        x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
        bw = max(0.0, x2 - x1)
        bh = max(0.0, y2 - y1)
        area_ratio = (bw * bh) / (w * h + 1e-6)

        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        in_path = (x_min <= cx <= x_max) and (y_min <= cy <= y_max)

        prev = prev_area.get(label, None)
        growth = (area_ratio / prev) if (prev and prev > 1e-6) else 1.0

        # base level by area
        level = 0
        if area_ratio >= TH_L3:
            level = 3
        elif area_ratio >= TH_L2:
            level = 2
        elif area_ratio >= TH_L1 and in_path:
            level = 1

        # boost by in-path
        if in_path and level > 0:
            level = min(3, level + 1)

        # boost by fast growth
        if growth >= GROWTH_BOOST and level > 0:
            level = min(3, level + 1)

        # update curr max
        curr_area[label] = max(curr_area.get(label, 0.0), area_ratio)

        if level == 0:
            continue

        cand = {
            "level": int(level),
            "label": label,
            "area_ratio": float(area_ratio),
            "growth": float(growth),
            "in_path": bool(in_path),
            "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
        }

        if best is None:
            best = cand
        else:
            # prefer higher level, then larger area_ratio
            if (cand["level"] > best["level"]) or (
                cand["level"] == best["level"] and cand["area_ratio"] > best["area_ratio"]
            ):
                best = cand

    if best is None:
        return 0, "", None

    level = best["level"]
    text = ALERT_TEXT.get(level, "")
    return level, text, best


# =========================
# 9) Capture Loop + YOLO Main Loop (adds HUD + stats)
# =========================
def capture_loop():
    global latest_raw_frame, latest_raw_ts, latest_shape

    session = requests.Session()
    next_fetch = 0.0
    backoff = CAPTURE_BACKOFF_BASE
    fail_count = 0

    print("Capture loop started:", ESP32_CAPTURE_URL)

    while True:
        now = time.time()
        if now < next_fetch:
            time.sleep(0.002)
            continue
        next_fetch = now + FETCH_INTERVAL

        frame = fetch_capture_frame(session)
        if frame is None:
            fail_count += 1
            if fail_count % CAPTURE_FAIL_LOG_EVERY == 0:
                print(f"Capture failed x{fail_count}")
            time.sleep(backoff)
            backoff = min(CAPTURE_BACKOFF_MAX, backoff * 1.5)
            continue

        backoff = CAPTURE_BACKOFF_BASE
        fail_count = 0

        h, w = frame.shape[:2]
        with lock:
            latest_raw_frame = frame
            latest_raw_ts = time.time()
            latest_shape = (h, w)


def audio_sender_loop():
    global latest_last_send_ts, latest_last_send_ok

    while True:
        wav_path = audio_queue.get()
        ok = send_wav_to_esp32(wav_path)
        with lock:
            latest_last_send_ok = ok
            if ok:
                latest_last_send_ts = time.time()
        audio_queue.task_done()


def enqueue_audio(level: int) -> bool:
    try:
        if audio_queue.full():
            try:
                audio_queue.get_nowait()
                audio_queue.task_done()
            except queue.Empty:
                pass
        audio_queue.put_nowait(AUDIO_MAP[level])
        return True
    except queue.Full:
        return False


def yolo_loop():
    global latest_frame_jpg, latest_alert_level, prev_max_area_ratio
    global latest_ts, latest_shape, latest_boxes, latest_count
    global latest_infer_ms, latest_delay_ms, latest_fps_infer
    global latest_alert_text, latest_alert_target, latest_should_notify
    global alert_on_count, alert_off_count, stable_alert_level, stable_alert_text
    global stable_alert_target, last_alert_emit_ts

    next_infer = 0.0

    print("?YOLO loop started, capture:", ESP32_CAPTURE_URL, "tcp:", f"{ESP32_IP}:{TTS_TCP_PORT}")

    while True:
        now = time.time()

        # ---- infer throttling
        if now < next_infer:
            time.sleep(0.003)
            continue
        next_infer = now + INFER_INTERVAL

        with lock:
            frame = latest_raw_frame
            frame_ts = latest_raw_ts

        if frame is None:
            time.sleep(0.01)
            continue

        h, w = frame.shape[:2]

        # ---- infer + timing
        t0 = time.time()
        results = model.predict(
            frame, imgsz=IMG_SIZE, conf=CONF, iou=IOU,
            verbose=False, device=MODEL_DEVICE, half=MODEL_HALF
        )
        t1 = time.time()

        infer_ms = (t1 - t0) * 1000.0
        fps_infer = 1000.0 / infer_ms if infer_ms > 0 else 0.0
        delay_ms = (time.time() - frame_ts) * 1000.0 if frame_ts > 0 else 0.0

        r = results[0]
        boxes: List[Dict[str, Any]] = []

        if r.boxes is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            clss = r.boxes.cls.cpu().numpy().astype(int)
            names = model.names

            for (x1, y1, x2, y2), c, k in zip(xyxy, confs, clss):
                boxes.append({
                    "label": names.get(int(k), str(int(k))),
                    "conf": float(c),
                    "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
                })

        count = len(boxes)

        # ---- alert compute
        curr_area: Dict[str, float] = {}
        level_raw, text_raw, target_raw = compute_alert(boxes, w, h, prev_max_area_ratio, curr_area)
        prev_max_area_ratio = curr_area

        if level_raw > 0:
            alert_on_count += 1
            alert_off_count = 0
            if alert_on_count >= ALERT_CONSECUTIVE_ON:
                stable_alert_level = level_raw
                stable_alert_text = text_raw
                stable_alert_target = target_raw
        else:
            alert_off_count += 1
            alert_on_count = 0
            if alert_off_count >= ALERT_CONSECUTIVE_OFF:
                stable_alert_level = 0
                stable_alert_text = ""
                stable_alert_target = None

        level = stable_alert_level
        text = stable_alert_text
        target = stable_alert_target

        # ---- cooldown + enqueue audio (rate-limited)
        should_notify = False
        if level > 0:
            cd = ALERT_COOLDOWN.get(level, 1.0)
            repeat_min = ALERT_REPEAT_MIN.get(level, 1.0)
            now_ts = time.time()
            if (now_ts - last_alert_time[level]) >= cd and (now_ts - last_alert_emit_ts) >= repeat_min:
                if enqueue_audio(level):
                    last_alert_time[level] = now_ts
                    last_alert_emit_ts = now_ts
                    should_notify = True

        # ---- draw (boxes + HUD)
        annotated = r.plot()

        # HUD text (top-left)
        cv2.putText(annotated, f"FPS(infer): {fps_infer:.1f}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated, f"Delay: {delay_ms:.0f} ms", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated, f"Count: {count}", (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if level > 0:
            cv2.putText(annotated, f"ALERT L{level}", (10, 105),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)
            cv2.putText(annotated, text, (10, 135),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

        ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        jpg = buf.tobytes() if ok else None

        with lock:
            latest_ts = time.time()
            latest_boxes = boxes
            latest_count = count

            latest_infer_ms = infer_ms
            latest_fps_infer = fps_infer
            latest_delay_ms = delay_ms

            latest_alert_level = level
            latest_alert_text = text
            latest_alert_target = target
            latest_should_notify = should_notify

            latest_frame_jpg = jpg
            frame_cond.notify_all()
# =========================
# 10) Flask Endpoints
# =========================
@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.get("/detect")
def detect():
    with lock:
        return jsonify({
            "ts": latest_ts,
            "shape": {"h": latest_shape[0], "w": latest_shape[1]},
            "count": latest_count,
            "infer_ms": latest_infer_ms,
            "fps_infer": latest_fps_infer,
            "delay_ms": latest_delay_ms,

            "alert_level": latest_alert_level,
            "alert_text": latest_alert_text,
            "alert_target": latest_alert_target,
            "should_notify": latest_should_notify,
            "last_send_ts": latest_last_send_ts,
            "last_send_ok": latest_last_send_ok,
        })

@app.route("/video")
def video():
    def gen():
        # Pre-generate placeholder
        import cv2
        import numpy as np
        placeholder = np.zeros((320, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, "WAITING FOR CAMERA...", (20, 160), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        _, placeholder_jpg = cv2.imencode(".jpg", placeholder)
        placeholder_bytes = placeholder_jpg.tobytes()

        while True:
            with frame_cond:
                # Wait up to 0.5s for a new frame
                frame_cond.wait(timeout=0.5)
                frame = latest_frame_jpg
            
            if frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" +
                       frame + b"\r\n")
            else:
                # If timeout or no frame, send placeholder
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(placeholder_bytes)).encode() + b"\r\n\r\n" +
                       placeholder_bytes + b"\r\n")

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


# =========================
# 11) Main
# =========================
if __name__ == "__main__":
    for lvl, p in AUDIO_MAP.items():
        if not p.exists():
            print(f"?Missing audio for level {lvl}: {p}")
    try:
        dummy = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
        model.predict(dummy, imgsz=IMG_SIZE, conf=CONF, iou=IOU,
                      verbose=False, device=MODEL_DEVICE, half=MODEL_HALF)
    except Exception as e:
        print(f"Model warmup skipped: {e}")
    print("?Final Assistive Vision Server Started")
    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=audio_sender_loop, daemon=True).start()
    threading.Thread(target=yolo_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=SERVER_PORT, threaded=True)
