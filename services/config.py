import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

# =========================
# 基础路径配置
# =========================
BASE_DIR = Path(__file__).resolve().parent
# 音频文件目录，相对于 services 包的上一级
AUDIO_DIR = BASE_DIR.parent / "audio"

# =========================
# ESP32 与网络配置
# =========================
# ESP32 的 IP 地址，默认为开发板 IP，可通过 .env 覆盖
ESP32_IP = os.getenv("ESP32_IP", "192.168.132.244")
# ESP32 抓拍图片的 URL
ESP32_CAPTURE_URL = f"http://{ESP32_IP}/capture"
# 语音合成 (TTS) TCP 端口
TTS_TCP_PORT = int(os.getenv("TTS_TCP_PORT", 23456))
# 本地 Flask 服务器端口
SERVER_PORT = int(os.getenv("SERVER_PORT", 5000))

# =========================
# YOLO 模型配置
# =========================
MODEL_PATH = "yolov8n.pt"
IMG_SIZE = 320         # 推理图片大小
CONF_THRESHOLD = 0.35  # 置信度阈值
IOU_THRESHOLD = 0.5    # NMS IOU 阈值

# =========================
# 运行时流控配置
# =========================
FETCH_INTERVAL = 0.04   # 抓取帧的最小间隔 (秒) -> 目标 25 FPS
INFER_INTERVAL = 0.05   # 推理的最小间隔 (秒) -> 目标 20 FPS
CAPTURE_BACKOFF_BASE = 0.03 # 抓取失败后的基础退避时间
CAPTURE_BACKOFF_MAX = 0.5   # 最大退避时间
CAPTURE_FAIL_LOG_EVERY = 30 # 每失败多少次打印一次日志
JPEG_QUALITY = 65       # HUD 推流的 JPEG 质量 (降低以加速编码)

# =========================
# CUDA 加速配置
# =========================
USE_HALF_PRECISION = True  # 在 CUDA 下使用 FP16 推理，可提速 20-40%

# =========================
# 风险评估参数 (Risk Estimation)
# =========================
# 定义用户前方的“行走路径”区域 (归一化坐标)
PATH_X_MIN, PATH_X_MAX = 0.30, 0.70
PATH_Y_MIN, PATH_Y_MAX = 0.20, 0.95

# =========================
# 警报阈值 (Alert Thresholds)
# =========================
# 面积占比阈值，用于判断物体距离
TH_L1 = 0.02  # Level 1: 关注
TH_L2 = 0.06  # Level 2: 警惕
TH_L3 = 0.14  # Level 3: 危险
GROWTH_BOOST = 1.25 # 物体面积增长率阈值，超过此值提升警报等级

# 关注的检测类别
ALERT_CLASSES = {"person"}

# 不同等级的语音播报冷却时间 (秒)
ALERT_COOLDOWN = {1: 2.0, 2: 1.0, 3: 0.4}
# 相同警报的最小重复间隔 (秒)
ALERT_REPEAT_MIN = {1: 5.0, 2: 3.0, 3: 2.0}
# 连续多少帧触发才确认为“开启”
ALERT_CONSECUTIVE_ON = 3
# 连续多少帧未触发才确认为“关闭”
ALERT_CONSECUTIVE_OFF = 4

# 警报文本 (英文，避免编码问题)
ALERT_TEXT = {
    1: "Person ahead",
    2: "Watch out",
    3: "Danger! Stop",
}

AUDIO_MAP = {
    1: AUDIO_DIR / "l1.wav",
    2: AUDIO_DIR / "l2.wav",
    3: AUDIO_DIR / "l3.wav",
}

# =========================
# VAD (语音活动检测) 配置
# =========================
VAD_THRESHOLD = 3200        # RMS 能量阈值，高于此值认为在说话 (根据麦克风调整)
VAD_SILENCE_LIMIT = 1.0    # 静音持续多久认为说话结束 (秒)
VAD_DEBUG = True           # 是否打印 VAD 调试日志

# =========================
# Omni 服务配置
# =========================
USE_OMNI = False  # True: 使用 qwen3-omni-flash-realtime, False: 使用传统 VoiceAssistant
OMNI_OUTPUT_HZ = int(os.getenv("OMNI_OUTPUT_HZ", 24000))  # Omni 输出音频采样率
OMNI_TARGET_HZ = int(os.getenv("OMNI_TARGET_HZ", 16000))  # 本地播放/ESP32 目标采样率

# =========================
# 寻物模式配置 (Search Mode)
# =========================
# 可搜索的物品类别 (COCO 类名)
SEARCHABLE_CLASSES = {
    "cup", "bottle", "cell phone", "remote", "book", 
    "scissors", "keyboard", "mouse", "laptop", "backpack",
    "umbrella", "handbag", "suitcase", "clock", "vase"
}

# 中文别名映射 -> COCO 类名
SEARCH_ALIASES = {
    "水杯": "cup", "杯子": "cup", "瓶子": "bottle", 
    "手机": "cell phone", "电话": "cell phone",
    "遥控器": "remote", "书": "book", "剪刀": "scissors",
    "键盘": "keyboard", "鼠标": "mouse", "电脑": "laptop",
    "背包": "backpack", "伞": "umbrella", "包": "handbag",
    "箱子": "suitcase", "钟": "clock", "花瓶": "vase"
}

# 盖格计数器哔哔声间隔 (秒)
GEIGER_INTERVAL_FAR = 1.0    # 目标较远
GEIGER_INTERVAL_MID = 0.3    # 目标中等距离
GEIGER_INTERVAL_NEAR = 0.1   # 目标很近

# 面积占比阈值 (用于判断距离)
GEIGER_AREA_MID = 0.03       # 中等距离阈值
GEIGER_AREA_NEAR = 0.10      # 近距离阈值

# 哔哔声参数
BEEP_FREQ = 1000             # 哔哔声频率 (Hz)
BEEP_DURATION_MS = 50        # 哔哔声时长 (ms)
BEEP_SAMPLE_RATE = 16000     # 采样率
