#include "esp_camera.h"
#include <WiFi.h>

#include "driver/i2s.h"

// =======================
// A) 你原来的引脚定义（不动）
// =======================
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

// =======================
// B) Wi-Fi（不动）
// =======================
const char *ssid = "genius_no.3";
const char *password = "meiyoumima";

void startCameraServer();
void setupLedFlash();

// ============================================================
// ✅ 新增 1：MAX98357A(I2S) + TCP 音频服务器（23456）
// ============================================================

// 你的接线（保持不变）
// DIN -> D10, BCLK -> D8, LRC -> D9
static const int I2S_DOUT = D10;
static const int I2S_BCLK = D8;
static const int I2S_LRC  = D9;

static const i2s_port_t I2S_PORT = I2S_NUM_0;

// TCP 端口（PC 推 PCM 用）
static const uint16_t TTS_TCP_PORT = 23456;
WiFiServer ttsServer(TTS_TCP_PORT);

// 当前 I2S 参数（随 header 可动态调整）
static int g_sr = 16000;
static int g_ch = 1;
static int g_bits = 16;

static uint32_t le_u32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static uint16_t le_u16(const uint8_t *p) {
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static bool read_exact(WiFiClient &c, uint8_t *buf, size_t n, uint32_t timeout_ms) {
  uint32_t start = millis();
  size_t got = 0;
  while (got < n) {
    if (!c.connected()) return false;
    int avail = c.available();
    if (avail > 0) {
      int r = c.read(buf + got, n - got);
      if (r > 0) got += (size_t)r;
    } else {
      if (millis() - start > timeout_ms) return false;
      delay(1);
    }
  }
  return true;
}

static void i2s_configure(int sr, int ch, int bits) {
  // 为稳定：先卸载再安装
  i2s_driver_uninstall(I2S_PORT);

  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = sr;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;   // 本方案只支持 16bit
  cfg.channel_format = (ch == 2) ? I2S_CHANNEL_FMT_RIGHT_LEFT : I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;

  i2s_pin_config_t pin = {};
  pin.bck_io_num = I2S_BCLK;
  pin.ws_io_num = I2S_LRC;
  pin.data_out_num = I2S_DOUT;
  pin.data_in_num = I2S_PIN_NO_CHANGE;

  i2s_driver_install(I2S_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin);
  i2s_zero_dma_buffer(I2S_PORT);

  g_sr = sr;
  g_ch = ch;
  g_bits = bits;

  Serial.printf("I2S ready: sr=%d ch=%d bits=%d\n", g_sr, g_ch, g_bits);
}

void audio_task(void *param) {
  Serial.printf("TTS TCP server listening on %u\n", TTS_TCP_PORT);
  ttsServer.begin();
  ttsServer.setNoDelay(true);

  uint8_t header[16];
  static uint8_t netbuf[2048];

  while (true) {
    WiFiClient client = ttsServer.available();
    if (!client) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    client.setNoDelay(true);
    Serial.println("TTS: client connected");

    // 读 header（PCM1 + sr(u32) + ch(u16) + bits(u16) + len(u32)）
    if (!read_exact(client, header, sizeof(header), 3000)) {
      Serial.println("TTS: header timeout");
      client.stop();
      continue;
    }
    if (!(header[0]=='P' && header[1]=='C' && header[2]=='M' && header[3]=='1')) {
      Serial.println("TTS: bad magic");
      client.stop();
      continue;
    }

    uint32_t sr   = le_u32(header + 4);
    uint16_t ch   = le_u16(header + 8);
    uint16_t bits = le_u16(header + 10);
    uint32_t len  = le_u32(header + 12);

    // 容错
    if (sr < 8000 || sr > 48000) sr = 16000;
    if (ch != 1 && ch != 2) ch = 1;
    if (bits != 16) bits = 16;

    Serial.printf("TTS: start sr=%u ch=%u bits=%u len=%u\n", sr, ch, bits, len);

    // 如参数变化则重配 I2S
    if ((int)sr != g_sr || (int)ch != g_ch || (int)bits != g_bits) {
      i2s_configure((int)sr, (int)ch, (int)bits);
    } else {
      i2s_zero_dma_buffer(I2S_PORT);
    }

    uint32_t remaining = len;
    while (remaining > 0 && client.connected()) {
      size_t want = remaining > sizeof(netbuf) ? sizeof(netbuf) : remaining;
      if (!read_exact(client, netbuf, want, 3000)) {
        Serial.println("TTS: payload timeout");
        break;
      }
      size_t written = 0;
      i2s_write(I2S_PORT, (const char*)netbuf, want, &written, portMAX_DELAY);
      remaining -= (uint32_t)want;
    }

    Serial.println("TTS: done");
    client.stop();
  }
}

// ============================================================
// C) 你的原 setup（只做“增量插入”，不破坏原功能）
// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  // ✅ 新增：先把 I2S 起起来（默认 16k/mono/16bit）
  i2s_configure(16000, 1, 16);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
    s->set_brightness(s, 1);
    s->set_saturation(s, -2);
  }
  if (config.pixel_format == PIXFORMAT_JPEG) {
    s->set_framesize(s, FRAMESIZE_QVGA);
  }

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  // 先启动摄像头 WebServer（保留原功能）
  startCameraServer();

  // ✅ 新增：启动音频任务（不会阻塞你的摄像头服务）
  BaseType_t ok = xTaskCreatePinnedToCore(audio_task, "audio_task", 12288, NULL, 3, NULL, 0);
  Serial.printf("audio_task create: %s\n", ok == pdPASS ? "OK" : "FAIL");

  Serial.print("Camera Ready! Use 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("' to connect");
  Serial.printf("TTS TCP port: %u\n", TTS_TCP_PORT);
}

void loop() {
  // 保留原行为
  delay(10000);
}