/**
 * XIAO ESP32S3 Sense - 终极合体版
 * 功能：
 * 1. 摄像头推流 (Port 80/81)
 * 2. 麦克风录音 -> 推送到 PC (Port 23457)
 * 3. 接收 PC 音频 -> 扬声器播放 (Port 23456)
 * 4. 解决 I2S 冲突与回声问题
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include <ESP_I2S.h>

// 参考代码用法：无参数构造
I2SClass I2S_Mic; 
I2SClass I2S_Spk; 

// 恢复 Speaker 相关定义
#define SPK_BCLK      7
// ...
#define SPK_LRC       8
#define SPK_DOUT      9
// #define SPK_I2S_PORT     I2S_NUM_1 // 不再需要，通过对象管理

// ================= 用户配置区 (请修改) =================
const char *ssid = "genius_no.3";
const char *password = "meiyoumima";
const char* PC_HOST = "192.168.132.5"; // 电脑 IP
const int PC_MIC_PORT = 23457;         // 电脑接收麦克风端口
const int TTS_SERVER_PORT = 23456;     // ESP32 接收音频端口
// =======================================================

// --- 摄像头引脚 ---
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

// --- 扬声器 (MAX98357A) ---
// D8(BCLK), D9(LRC), D10(DOUT)
#define SPK_BCLK      7
#define SPK_LRC       8
#define SPK_DOUT      9

// --- 麦克风 (板载 PDM) ---
// 根据 XIAO ESP32S3 Sense 官方规格：
// PDM_CLK = GPIO42, PDM_DATA = GPIO41
#define MIC_CLK       42
#define MIC_SD        41 

// ⚠️ 关键修正：端口分配
// 麦克风必须用 I2S_NUM_0 (硬件限制)
#define MIC_I2S_PORT     I2S_NUM_0
// 扬声器用 I2S_NUM_1
#define SPK_I2S_PORT     I2S_NUM_1

// 全局标志位：防止自己录到自己的声音
volatile bool is_playing_tts = false;

// ================= I2S 配置函数 =================

void config_mic_i2s() {
    I2S_Mic.setPinsPdmRx(MIC_CLK, MIC_SD);
    // PDM RX, 16000Hz, 16bit, Mono
    if (!I2S_Mic.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
      Serial.println("❌ Failed to initialize I2S for Mic!");
    } else {
      Serial.println("✅ Mic Initialized via ESP_I2S (I2S0)");
    }
}

void config_speaker_i2s() {
    // MAX98357A: 标准 I2S, TX, 16k, 16bit, Mono
    I2S_Spk.setPins(SPK_BCLK, SPK_LRC, SPK_DOUT, -1); // SCK, WS, SDOUT, SDIN(unused)
    
    // 参考代码使用: I2S_MODE_STD
    if (!I2S_Spk.begin(I2S_MODE_STD, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
         Serial.println("❌ Failed to initialize I2S for Speaker!");
    } else {
         Serial.println("✅ Speaker Initialized via ESP_I2S (I2S1)");
         // 预填静音
         // I2S_Spk.write((uint8_t*)calloc(1024, 1), 1024);
    }
}

// ================= 摄像头 HTTP 服务 =================

httpd_handle_t stream_httpd = NULL;

static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    char part_buf[64];
    static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
    static const char* _STREAM_BOUNDARY = "\r\n--123456789000000000000987654321\r\n";
    static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            res = ESP_FAIL;
        } else {
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res == ESP_OK) {
                size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
                res = httpd_resp_send_chunk(req, part_buf, hlen);
            }
            if (res == ESP_OK) {
                res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
            }
            esp_camera_fb_return(fb);
            if (res != ESP_OK) break;
        }
        // 小延迟给音频任务让路
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    return res;
}

// 单帧抓取处理器 (供后端 YOLO 推理使用)
static esp_err_t capture_handler(httpd_req_t *req) {
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    
    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    return res;
}

httpd_handle_t capture_httpd = NULL;

void startCameraServer() {
    // 启动流媒体服务 (端口 81)
    httpd_config_t stream_config = HTTPD_DEFAULT_CONFIG();
    stream_config.server_port = 81; 
    stream_config.ctrl_port = 32768;

    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&stream_httpd, &stream_config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        Serial.println("✅ Camera Stream: http://IP:81/stream");
    }

    // 启动抓取服务 (端口 80)
    httpd_config_t capture_config = HTTPD_DEFAULT_CONFIG();
    capture_config.server_port = 80;
    capture_config.ctrl_port = 32769;

    httpd_uri_t capture_uri = {
        .uri       = "/capture",
        .method    = HTTP_GET,
        .handler   = capture_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&capture_httpd, &capture_config) == ESP_OK) {
        httpd_register_uri_handler(capture_httpd, &capture_uri);
        Serial.println("✅ Camera Capture: http://IP:80/capture");
    }
}

// ================= 任务逻辑 =================

// 任务 A: 麦克风录音 -> TCP 发送
void mic_task(void *param) {
    Serial.println("🎙️ Mic Task Started");
    while (WiFi.status() != WL_CONNECTED) vTaskDelay(1000);

    WiFiClient client;
    uint8_t buffer[1024];
    size_t bytes_read = 0;
    
    // 调试用变量
    unsigned long lastDebugTime = 0;
    size_t totalBytesSent = 0;

    while (true) {
        // 1. 如果正在播放 TTS，或者未连接 PC，则暂停
        if (is_playing_tts || !client.connected()) {
            if (!client.connected()) {
                if (client.connect(PC_HOST, PC_MIC_PORT)) {
                    Serial.println("🔗 Mic Connected to PC");
                    Serial.println("🎤 Starting audio recording...");
                    client.setNoDelay(true);
                } else {
                    Serial.print("❌ Mic connect fail: "); Serial.println(PC_HOST);
                    vTaskDelay(2000);
                }
            }
            // 播放期间清空 Mic 缓存，防止积压
            // 播放期间清空 Mic 缓存，防止积压
            if (is_playing_tts) {
                // Legacy i2s_read removed
                // i2s_read(MIC_I2S_PORT, buffer, sizeof(buffer), &bytes_read, 10);
                vTaskDelay(100); 
            }
            continue;
        }

        // 2. 录音 (使用 ESP_I2S 库)
        // 我们需要手动填充 buffer，因为 I2S.read() 返回单个样本 (int16_t)
        // 或者如果库支持 readBytes，我们可以用它。大多数 Arduino Stream 支持。
        // 这里为了稳妥，且模仿参考代码的增益逻辑，我们手动读取 loop
        
        int samples_to_read = sizeof(buffer) / 2; // 16bit samples
        int samples_read = 0;
        int16_t* pcm_buffer = (int16_t*)buffer;
        
        // 尝试读取一帧数据的量 (非阻塞或带超时)
        // ESP_I2S 库内部 buffer 应该足够大。
        // 我们可以直接用 I2S.readBytes，但参考代码用了 read() + 增益。
        
        // 简单的批量读取 + 软件增益
        size_t bytes_available = I2S_Mic.available();
        if (bytes_available > 0) {
           // 限制单次读取量，防止 buffer 溢出
           if(bytes_available > sizeof(buffer)) bytes_available = sizeof(buffer);
           
           // 使用 readBytes 批量读取原始数据 (注意：ESP_I2S 的 readBytes 可能返回字节)
           // 参考代码: int16_t sample = I2S.read();
           // 既然参考代码一个个读，我们也一个个读，虽然效率低点但稳妥。
           // 为了效率，我们还是尝试直接读如果不为空
           
           for (int i=0; i < bytes_available/2; i++) {
               int16_t sample = I2S_Mic.read();
               // 增益处理
               int32_t val = sample << 1; // 放大 2 倍 (原 16 倍太大了)
               if(val > 32767) val = 32767;
               if(val < -32768) val = -32768;
               pcm_buffer[i] = (int16_t)val;
           }
           
           size_t bytes_got = (bytes_available / 2) * 2; // 确保偶数
           if (bytes_got > 0) {
               size_t written = client.write(buffer, bytes_got);
               totalBytesSent += written;
               
               if (millis() - lastDebugTime >= 2000) {
                    Serial.printf("📤 Audio sent: %d bytes/2s\n", totalBytesSent);
                    totalBytesSent = 0;
                    lastDebugTime = millis();
               }
           }
        } else {
             // Debug starvation
             static unsigned long lastStarve = 0;
             if (millis() - lastStarve > 5000) {
                 Serial.printf("⚠️ Mic Starvation: available=0\n");
                 lastStarve = millis();
             }
             vTaskDelay(5); // 没有数据就稍微歇一下
        }
        
    }
}

// 任务 B: 接收 TTS -> 扬声器播放
// 任务 B: 接收 TTS -> 扬声器播放
// 任务 B: 接收 TTS -> 扬声器播放
WiFiServer ttsServer(TTS_SERVER_PORT);
void tts_task(void *param) {
    ttsServer.begin();
    ttsServer.setNoDelay(true);
    Serial.printf("🔊 TTS Server Listening on %d\n", TTS_SERVER_PORT);

    uint8_t header[16]; // PCM1 Header
    static uint8_t netbuf[1024];

    while (true) {
        WiFiClient client = ttsServer.available();
        if (client) {
            Serial.println("📥 Receiving TTS Audio...");
            is_playing_tts = true; // 🔴 锁定麦克风

            while(client.connected()) {
                // 读取 Header (16 bytes)
                size_t got = 0;
                unsigned long headerStartTime = millis();
                while(got < 16 && client.connected()) {
                    if(client.available()) {
                        got += client.read(header + got, 16 - got);
                    } else {
                        delay(1);
                        // 超时检测：5秒内没收到完整 header
                        if(millis() - headerStartTime > 5000) {
                            Serial.println("⚠️ Header timeout!");
                            break;
                        }
                    }
                }
                if(got < 16) {
                    Serial.printf("❌ Header incomplete: got %d bytes\n", got);
                    break;
                }

                // 打印 header 内容用于调试
                if(header[0] != 'P') {
                    Serial.printf("❌ Invalid magic: 0x%02X (expected 'P')\n", header[0]);
                    break;
                }
                
                // 解析长度
                uint32_t data_len = (uint32_t)header[12] | ((uint32_t)header[13]<<8) | ((uint32_t)header[14]<<16) | ((uint32_t)header[15]<<24);
                Serial.printf("🔊 Playing %d bytes (%.2f sec)...\n", data_len, (float)data_len / 32000.0);
                
                // 播放 PCM 数据
                size_t remaining = data_len;
                size_t total_written = 0;
                while(remaining > 0 && client.connected()) {
                    size_t to_read = (remaining > sizeof(netbuf)) ? sizeof(netbuf) : remaining;
                    size_t net_got = 0;
                    unsigned long dataStartTime = millis();
                    while(net_got < to_read && client.connected()) {
                         if(client.available()) {
                             net_got += client.read(netbuf + net_got, to_read - net_got);
                         } else {
                             delay(1);
                             // 超时检测
                             if(millis() - dataStartTime > 5000) {
                                 Serial.printf("⚠️ Data timeout at %d/%d bytes\n", total_written, data_len);
                                 break;
                             }
                         }
                    }
                    
                    if(net_got == 0) break; // 连接断开
                    
                    // 写入 I2S 播放
                    I2S_Spk.write(netbuf, net_got);
                    
                    remaining -= net_got;
                    total_written += net_got;
                }
                Serial.printf("✅ Played %d/%d bytes\n", total_written, data_len);
                // 短暂静音防止爆音: 写入一些静音帧
                uint8_t silence[512] = {0};
                I2S_Spk.write(silence, sizeof(silence));
            }
            
            client.stop();
            is_playing_tts = false; // 🟢 解锁麦克风
            Serial.println("✅ TTS Done");
        }
        vTaskDelay(20);
    }
}

// ================= Setup =================

void setup() {
    Serial.begin(115200);
    Serial.println("\n🚀 System Booting...");

    // 1. 初始化摄像头 (必须第一个!)
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM; config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.frame_size = FRAMESIZE_VGA;  // 640x480 优化帧率
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 15;  // 适中质量，加快编码
    config.fb_count = 1;
    
    if(psramFound()){
        config.jpeg_quality = 15;
        config.fb_count = 2;
        config.grab_mode = CAMERA_GRAB_LATEST;
    }
    
    if(esp_camera_init(&config) != ESP_OK) {
        Serial.println("❌ Camera Failed");
        while(1) delay(100);
    }
    Serial.println("📷 Camera Ready");

    // 2. 初始化网络
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
    }
    Serial.println("\n📶 WiFi Connected");

    // 3. 初始化音频 (注意顺序: 先 Mic 后 Speaker，参考 compile.ino)
    config_mic_i2s();     // I2S0 (ESP_I2S)
    config_speaker_i2s(); // I2S1 (ESP_I2S)

    // 4. 启动服务与任务
    startCameraServer();
    
    // Core 0 处理音频播放 (负载低)
    xTaskCreatePinnedToCore(tts_task, "tts_task", 4096, NULL, 5, NULL, 0);
    // Core 1 处理麦克风 (需要稳定)
    xTaskCreatePinnedToCore(mic_task, "mic_task", 4096, NULL, 5, NULL, 1);
}

void loop() {
    vTaskDelay(10000); // 主循环空闲
}