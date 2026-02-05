# A.VISION - 智能辅助视觉中枢 (Smart Assistive Vision Hub)

**A.VISION** 是一个专为视障人士设计的综合辅助系统。它以 **ESP32-S3 Sense** 作为感知终端，利用 **PC/服务器** 的强大算力进行实时计算机视觉分析 (YOLOv8) 和多模态 AI 交互 (OpenAI/Qwen)，并通过低延迟的音频流实现双向语音通信。

---

## 🏗️ 系统架构

系统采用 **端云协同 (Edge-Cloud Collaboration)** 架构：

```mermaid
graph TD
    subgraph "感知终端 (ESP32-S3 Sense)"
        Cam[Camera UXGA] -->|HTTP MJPEG (Port 81)| Srv[Stream Server]
        Mic[PDM Mic] -->|I2S0| MicTask
        MicTask -->|TCP Raw PCM (Port 23457)| PC_Mic
        
        PC_TTS -->|TCP PCM1 Protocol (Port 23456)| SpkTask
        SpkTask -->|I2S1| Spk[MAX98357A Speaker]
    end

    subgraph "计算中枢 (PC/Python)"
        Srv -.->|Fetch Frame| CamSvc[Camera Service]
        CamSvc --> State[(Global AppState)]
        
        State --> Vision[YOLOv8 Engine]
        Vision -->|Risk Level| State
        
        PC_Mic[Microphone Service] -->|WAV| VoiceAI[Voice Assistant]
        VoiceAI -->|STT Text| OpenAI[OpenAI / Qwen]
        OpenAI -->|Response Text| TTS_Engine[Edge-TTS / QwenRealtime]
        TTS_Engine -->|PCM Bytes| AudioSvc[Audio Service]
        AudioSvc --> PC_TTS
        
        Vision -->|Alert Audio| AudioSvc
    end

    subgraph "用户界面 (Web HUD)"
        State -->|Poll JSON| HUD[Neural Dark UI]
        State -->|MJPEG Stream| VideoElement
    end
```

---

## 🚀 核心特性

1.  **实时视觉避障 (Visual VSLAM/Collision Warning)**
    *   **核心模块**: `VisionService`
    *   使用 YOLOv8n 进行目标检测 (20+ FPS)。
    *   **动态风险评估**: 根据物体面积占比、是否在行进路径、面积增长率计算 Level 1-3 风险等级。
    *   **迟滞滤波 (Hysteresis)**: 防止警报频繁跳变。

2.  **多模态 AI 助理 (Multimodal AI Agent)**
    *   **核心模块**: `VoiceAssistant` (标准模式) 或 `OmniService` (极速模式)
    *   **视觉问答**: 用户问“前面有什么？”，系统自动截取当前帧并描述环境。
    *   **全双工语音**: 边录边传，本地 VAD (语音活动检测) 分句。
    *   **双模式支持**:
        *   **Standard**: STT (Aliyun/Google) -> LLM (OpenAI/Qwen-VL) -> TTS (EdgeTTS).
        *   **Omni**: 使用 `qwen-omni-flash-realtime` 实现毫秒级视频语音交互 (需配置 Feature Flag)。

3.  **🔍 寻物助手 (Object Finder) [NEW]**
    *   **核心模块**: `VoiceAssistant._parse_search_command()` + `VisionService.locate_target()`
    *   **语音触发**: 用户说"找水杯"、"帮我找手机"、"遥控器在哪"等。
    *   **盖格计数器反馈**: 目标物体越近，哔哔声越快（远:1s, 中:0.3s, 近:0.1s）。
    *   **支持物品**: 水杯、手机、遥控器、书、剪刀、键盘、鼠标、电脑、背包、伞等 15 种常见物品。
    *   **退出方式**: 说"停止"、"找到了"、"取消"。

4.  **极客风格 HUD (Neural Dark UI)**
    *   基于 Tailwind CSS + GSAP 动画，Glassmorphism 玻璃拟态设计。
    *   实时显示 FPS、延迟、推理状态、波形图。
    *   前端自动适配横竖屏。

---

## 🛠️ 硬件指南

### 1. 硬件清单
*   **主控**: Seeed XIAO ESP32S3 Sense (带扩展板)
*   **麦克风**: 板载 PDM 数字麦克风
*   **扬声器驱动**: MAX98357A I2S Amplifier
*   **扬声器**: 4Ω/8Ω 小喇叭

### 2. 引脚定义 (Pinout)
*(参考 `stm32code/esp32_firmware_mic.ino`)*

| 功能 | 组件 | 引脚/GPIO | 备注 |
| :--- | :--- | :--- | :--- |
| **Mic Data** | PDM Mic | GPIO 41 | I2S_NUM_0 |
| **Mic Clk** | PDM Mic | GPIO 42 | I2S_NUM_0 |
| **Spk BCLK** | MAX98357A | GPIO 7 (D8) | I2S_NUM_1 |
| **Spk LRC** | MAX98357A | GPIO 8 (D9) | I2S_NUM_1 |
| **Spk DOUT** | MAX98357A | GPIO 9 (D10) | I2S_NUM_1 |

---

## 💻 后端部署 (PC)

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置文件 (.env)
在项目根目录创建 `.env` 文件。**注意：IP 配置必须与您的局域网环境一致！**

```ini
# --- 网络配置 (CRITICAL) ---
server_port=5000         # 本地 Web 服务端口
esp32_ip=192.168.1.101   # [重要] ESP32 的 IP 地址

# --- AI 服务配置 ---
OPENAI_API_KEY=sk-xxxxxxxxxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-vl-max
```

### 3. 运行
使用模块化入口启动：
```bash
python main.py
```
*(注：`server_final.py` 为遗留版本，仅供参考)*

启动后访问: `http://localhost:5000`

---

## 📂 项目结构

```text
d:\glasses\
├── main.py                 # [入口] Flask 应用主入口，整合所有服务
├── server_final.py         # [遗留] 旧版单体服务器脚本 (仅供参考)
├── requirements.txt        # Python 依赖清单
├── .env                    # [配置] 环境变量 (需自行创建，参考 .env.example)
├── .env.example            # 环境变量模板
├── yolov8n.pt              # YOLOv8 预训练模型权重
│
├── services/               # [核心服务模块]
│   ├── __init__.py         # 包初始化
│   ├── config.py           # 配置加载与常量定义 (ESP32 IP、阈值、VAD 参数等)
│   ├── state.py            # 全局状态管理 (线程安全，支持寻物模式)
│   ├── vision_service.py   # YOLO 视觉推理与风险评估
│   ├── camera_service.py   # MJPEG 流相机服务 (连接 ESP32 Port 81)
│   ├── audio_service.py    # 音频流发送服务 (TCP PCM1 协议)
│   ├── microphone_service.py # 麦克风 TCP 服务端 (Port 23457，支持 VAD)
│   ├── voice_assistant.py  # 语音助手 (STT + LLM + TTS 标准模式)
│   ├── omni_service.py     # 全能模式 (qwen-omni-flash-realtime)
│   └── api_docs.py         # Swagger API 文档 (Flask-RESTX)
│
├── stm32code/              # [ESP32 固件]
│   ├── esp32_firmware_mic.ino  # 核心固件 (摄像头+麦克风+扬声器)
│   ├── speaker.cpp         # 扬声器驱动库
│   ├── speaker.h           # 扬声器驱动头文件
│   └── code.md             # 固件开发笔记
│
├── static/                 # [前端静态资源]
│   ├── app.js              # 前端逻辑 (状态轮询、UI 更新、动画)
│   └── style.css           # 样式表 (Glassmorphism 玻璃拟态设计)
│
├── templates/              # [Flask 模板]
│   └── index.html          # 主页面 (Neural Dark UI)
│
├── tests/                  # [自动化测试]
│   ├── __init__.py
│   ├── test_state.py       # AppState 状态管理单元测试
│   ├── test_vision_service.py  # VisionService 推理测试
│   └── test_frontend.py    # 前端 API 集成测试
│
├── audio/                  # [系统音效]
│   ├── l1.wav              # Level 1 警报音效
│   ├── l2.wav              # Level 2 警报音效
│   └── l3.wav              # Level 3 警报音效
│
└── recordings/             # [语音录音] (运行时自动创建)
```

---

## 🧪 开发者指南

### 1. 运行测试

项目使用 **pytest** 进行自动化测试：

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试模块
pytest tests/test_vision_service.py -v

# 运行并查看覆盖率 (需安装 pytest-cov)
pytest tests/ --cov=services --cov-report=html
```

测试套件包括：
- `test_state.py` - `AppState` 线程安全与状态管理
- `test_vision_service.py` - YOLO 推理与风险计算
- `test_frontend.py` - Flask API 端点集成测试

### 2. API 文档 (Swagger)

项目集成了 **Flask-RESTX** 自动生成 API 文档：

```
启动服务后访问: http://localhost:5000/api/docs
```

提供的端点：
| 端点 | 方法 | 描述 |
|:-----|:----:|:-----|
| `/health` | GET | 健康检查 |
| `/detect` | GET | 获取检测数据 (轮询接口) |
| `/video` | GET | MJPEG 视频流 |

### 3. 服务模块架构

```
┌─────────────────┐      ┌─────────────────┐
│  CameraService  │──────▶│     AppState    │◀───────┐
│   (MJPEG 流)    │       │   (全局状态)     │        │
└─────────────────┘       └────────┬────────┘        │
                                   │                  │
       ┌───────────────────────────┼──────────────────┤
       ▼                           ▼                  ▼
┌─────────────────┐      ┌─────────────────┐  ┌─────────────────┐
│  VisionService  │      │  VoiceAssistant │  │  AudioService   │
│   (YOLO 推理)    │      │  (STT+LLM+TTS)  │  │   (TCP 发送)    │
└─────────────────┘      └─────────────────┘  └─────────────────┘
                                   ▲
                                   │
                         ┌─────────────────┐
                         │MicrophoneService│
                         │   (TCP 接收)     │
                         └─────────────────┘
```

### 4. 代码规范

- **类型注解**: 所有公开方法应使用 Python type hints
- **文档字符串**: 使用中文编写 docstring，说明参数和返回值
- **线程安全**: 访问 `AppState` 时必须使用 `with state.lock:`
- **日志格式**: 使用 `[模块名]` 前缀，如 `[Camera]`、`[VAD]`

---

## ❓ 常见问题 (Troubleshooting)

1.  **ESP32 连不上电脑 (Connection Refused)**
    *   **关键检查**: `esp32_firmware_mic.ino` 中的 `PC_HOST` 必须修改为您当前电脑的 IP。
    *   确保防火墙放行端口 `23456` (Speaker) 和 `23457` (Mic)。

2.  **画面显示 "WAITING FOR CAMERA"**
    *   检查 `.env` 或 `config.py` 中的 `ESP32_IP` 是否正确。
    *   检查 ESP32 是否已上电并连接 WiFi。

3.  **Omni 模式未生效**
    *   该模式默认关闭。需在 `config.py` 中设置 `USE_OMNI = True` 并确保有相应的 API 权限。

---

## 🗺️ 功能路线图 (Roadmap)

以下是建议的未来功能方向：

| 优先级 | 功能 | 描述 |
|:------:|------|------|
| ⭐⭐⭐ | **文字识别 (OCR)** | 用户说"读一下"，识别画面中的文字并朗读（药瓶标签、路牌等） |
| ⭐⭐⭐ | **人脸识别** | 预存亲友照片，检测到熟人时语音提示"前方是张三" |
| ⭐⭐ | **空间音频** | 根据物体位置（左/中/右）在立体声中定位，用"3D声音"指引方向 |
| ⭐⭐ | **导航模式** | 结合手机 GPS，语音导航"前方100米右转" |
| ⭐⭐ | **场景记忆** | 记录"家"、"公司"等常去场所的布局，提供更精准的路径建议 |
| ⭐ | **跌倒检测** | 检测用户摔倒，自动发送求助短信 |
| ⭐ | **货币识别** | 识别纸币面额，帮助用户辨别钱款 |
| ⭐ | **颜色识别** | 用户问"这是什么颜色"，朗读衣物/物品颜色 |

---

## 📜 License
MIT License.
