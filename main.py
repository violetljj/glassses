import time
import threading
from flask import Flask, jsonify, Response, render_template
from flask.wrappers import Response as FlaskResponse
from flask_cors import CORS

from services import config
from services.state import AppState
from services.vision_service import VisionService
from services.audio_service import AudioService
from services.camera_service import CameraService
from services.microphone_service import MicrophoneService


from services.voice_assistant import VoiceAssistant

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# 注册 API 文档蓝图
from services.api_docs import init_api_docs
init_api_docs(app)

# 初始化核心服务组件
state = AppState()
vision = VisionService()
audio = AudioService(state)
camera = CameraService(state)
mic = MicrophoneService()

# 根据配置选择语音服务模式
voice_ai = VoiceAssistant(state, audio)
mic.set_callback(voice_ai.on_recording_complete)
print("Main: Using VoiceAssistant")


def processing_loop() -> None:
    """
    核心处理循环 (Backbone Loop)。

    职责：
    1. 从 state 获取最新帧。
    2. 调用 vision 服务进行推理 (YOLO)。
    3. 根据检测结果计算风险等级。
    4. 执行去抖动逻辑 (Stability Filter)，产生稳定的警报状态。
    5. 根据冷却时间决定是否推送语音警报。
    6. 绘制 HUD 并更新全局状态供前端查询。
    """
    print("Core processing loop started.")
    next_infer = 0.0

    while True:
        now = time.time()
        # 控制推理频率，避免过热
        if now < next_infer:
            time.sleep(0.003)
            continue
        next_infer = now + config.INFER_INTERVAL

        # 获取最新帧 (非阻塞)
        frame, frame_ts = state.get_frame()
        if frame is None:
            # 即使没有画面，也定期更新心跳，避免前端显示离线
            state.heartbeat()
            continue

        # 1. 视觉推理 (Inference)
        boxes, r, infer_ms = vision.predict(frame)

        # 2. 风险评估 (Risk Computation)
        level, text, target, curr_area = vision.compute_risk(
            boxes, state.latest_shape[1], state.latest_shape[0], state.prev_max_area_ratio
        )
        state.prev_max_area_ratio = curr_area

        # 3. 稳定性滤波 (Stability Filter / Hysteresis)
        # 避免警报在边缘频繁闪烁
        if level > 0:
            state.alert_on_count += 1
            state.alert_off_count = 0
            if state.alert_on_count >= config.ALERT_CONSECUTIVE_ON:
                state.stable_alert_level = level
                state.stable_alert_text = text
                state.stable_alert_target = target
        else:
            state.alert_off_count += 1
            state.alert_on_count = 0
            if state.alert_off_count >= config.ALERT_CONSECUTIVE_OFF:
                state.stable_alert_level = 0
                state.stable_alert_text = ""
                state.stable_alert_target = None

        # 4. 语音通知逻辑 (Audio Notification Logic)
        final_level = state.stable_alert_level
        should_notify = False
        
        # 寻物模式处理 (Search Mode Geiger Counter)
        if state.search_mode:
            # 在寻物模式下，定位目标物品
            target_info = vision.locate_target(
                boxes, state.search_target_class, 
                state.latest_shape[1], state.latest_shape[0]
            )
            state.update_search_target(target_info)
            
            if target_info:
                # 根据距离计算哔哔间隔
                distance = target_info["distance"]
                if distance == "near":
                    interval = config.GEIGER_INTERVAL_NEAR
                elif distance == "mid":
                    interval = config.GEIGER_INTERVAL_MID
                else:
                    interval = config.GEIGER_INTERVAL_FAR
                
                # 检查是否需要播放哔哔声
                if (now - state.search_last_beep_ts) >= interval:
                    audio.play_geiger_beep()
                    state.search_last_beep_ts = now
                    # 可选：打印调试信息
                    # print(f"[SearchMode] Beep! Target: {state.search_target_class}, Dir: {target_info['direction']}, Dist: {distance}")
        
        # 常规警报逻辑（寻物模式下暂停避障警报，避免干扰）
        elif final_level > 0:
            # DEBUG: Print why we are alarming
            if state.alert_on_count == config.ALERT_CONSECUTIVE_ON: # Only print on initial stable trigger or generally
                 print(f"[DEBUG] ALARM ACTIVE | Level: {final_level} | Target: {state.stable_alert_target} | Last emit: {now - state.last_alert_emit_ts:.1f}s")

            cd = config.ALERT_COOLDOWN.get(final_level, 1.0)
            repeat_min = config.ALERT_REPEAT_MIN.get(final_level, 1.0)
            # 检查 CD 和重复时间间隔
            # [Fix] 如果正在进行语音交互 (非 idle)，则暂停播放新的避障警报，避免干扰对话
            if state.latest_voice_status != "idle":
                 # Optional: print debug to show we are skipping
                 # print(f"[DEBUG] Skipping Alert L{final_level} due to Voice Active: {state.latest_voice_status}")
                 pass
            elif (now - state.last_alert_time[final_level]) >= cd and (now - state.last_alert_emit_ts) >= repeat_min:
                print(f"[DEBUG] Enqueueing Alert L{final_level}")
                audio.enqueue_alert(final_level)
                state.last_alert_time[final_level] = now
                state.last_alert_emit_ts = now
                should_notify = True

        # 5. UI 更新与 HUD 绘制 (UI Updates)
        fps = 1000.0 / infer_ms if infer_ms > 0 else 0.0
        delay = (time.time() - frame_ts) * 1000.0 if frame_ts > 0 else 0.0

        # 绘制带数据的 JPEG 图片
        jpg = vision.draw_hud(r.plot(), fps, delay, len(boxes), final_level, state.stable_alert_text)

        # 将结果发布到全局状态
        state.update_detection(boxes, infer_ms, fps, delay, jpg)
        state.update_alert(final_level, state.stable_alert_text, state.stable_alert_target, should_notify)

# =========================
# API 路由定义
# =========================

@app.route("/")
def index() -> str:
    """前端首页"""
    return render_template("index.html")

@app.get("/health")
def health() -> FlaskResponse:
    """健康检查接口"""
    return jsonify({"ok": True})

@app.get("/detect")
def detect() -> FlaskResponse:
    """
    前端轮询接口。
    返回当前的检测数据、状态指标和警报信息 (JSON)。
    """
    return jsonify(state.get_ui_data())

@app.route("/video")
def video() -> Response:
    """
    MJPEG 视频流接口。
    前端通过 <img src="/video"> 直接加载。
    如果在没有相机帧的情况下，发送一个包含“等待连接”文字的占位图。
    """
    def gen():
        print("DEBUG: Video generator started")
        # 预先生成一个黑色占位图
        import cv2
        import numpy as np
        placeholder = np.zeros((320, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, "WAITING FOR CAMERA...", (20, 160), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        _, placeholder_jpg = cv2.imencode(".jpg", placeholder)
        placeholder_bytes = placeholder_jpg.tobytes()

        while True:
            with state.frame_condition:
                # 等待新的一帧，超时 0.5 秒防止死锁或无响应
                notified = state.frame_condition.wait(timeout=0.5)
                frame = state.latest_frame_jpg

            if frame:
                # print("DEBUG: Yielding frame", len(frame))
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" +
                       frame + b"\r\n")
            else:
                # 只有在超时或依然没有帧时发送占位图
                print("DEBUG: Yielding placeholder")
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(placeholder_bytes)).encode() + b"\r\n\r\n" +
                       placeholder_bytes + b"\r\n")
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    print(f"Starting Assistive Vision Server on port {config.SERVER_PORT}")

    # 降低 Werkzeug 日志级别，屏蔽每次 HTTP 请求的日志
    import logging
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # 在后台线程启动核心处理循环
    threading.Thread(target=processing_loop, daemon=True).start()
    # 启动 Flask Web 服务
    app.run(host="0.0.0.0", port=config.SERVER_PORT, threaded=True)
