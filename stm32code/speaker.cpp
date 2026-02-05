#include "speaker.h"
#include <WiFi.h>
#include "driver/i2s.h"

// --- 扬声器配置 (MAX98357A) ---
// D8(BCLK), D9(LRC), D10(DOUT)
#define SPK_BCLK      7
#define SPK_LRC       8
#define SPK_DOUT      9
#define SPK_I2S_PORT  I2S_NUM_1

// TTS 端口
#define TTS_SERVER_PORT 23456

WiFiServer ttsServer(TTS_SERVER_PORT);

// 全局变量：控制麦克风暂停
extern volatile bool is_playing_tts;

void setupSpeaker() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S, 
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true
    };
    i2s_pin_config_t pin_config = {
        .bck_io_num = SPK_BCLK,
        .ws_io_num = SPK_LRC,
        .data_out_num = SPK_DOUT,
        .data_in_num = I2S_PIN_NO_CHANGE
    };
    
    // 安装驱动 (这里使用 driver/i2s.h 的原生函数)
    i2s_driver_install(SPK_I2S_PORT, &i2s_config, 0, NULL);
    i2s_set_pin(SPK_I2S_PORT, &pin_config);
    i2s_zero_dma_buffer(SPK_I2S_PORT);
    
    Serial.println("✅ Speaker Initialized on I2S1 (Native Driver)");
}

void speakerTask(void *param) {
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
                        if(millis() - headerStartTime > 5000) break;
                    }
                }
                if(got < 16) break;

                // 校验 header
                if(header[0] != 'P') {
                    Serial.printf("❌ Invalid magic: 0x%02X\n", header[0]);
                    break;
                }
                
                // 解析长度
                uint32_t data_len = (uint32_t)header[12] | ((uint32_t)header[13]<<8) | ((uint32_t)header[14]<<16) | ((uint32_t)header[15]<<24);
                Serial.printf("🔊 Playing %d bytes...\n", data_len);
                
                // 播放 loop
                size_t remaining = data_len;
                size_t written;
                
                while(remaining > 0 && client.connected()) {
                    size_t to_read = (remaining > sizeof(netbuf)) ? sizeof(netbuf) : remaining;
                    size_t net_got = 0;
                    unsigned long dataStartTime = millis();
                    
                    while(net_got < to_read && client.connected()) {
                         if(client.available()) {
                             net_got += client.read(netbuf + net_got, to_read - net_got);
                         } else {
                             delay(1);
                             if(millis() - dataStartTime > 5000) break;
                         }
                    }
                    if(net_got == 0) break; 
                    
                    // 原生写入 (阻塞)
                    i2s_write(SPK_I2S_PORT, netbuf, net_got, &written, portMAX_DELAY);
                    
                    remaining -= net_got;
                }
                // 短暂静音防止爆音
                i2s_zero_dma_buffer(SPK_I2S_PORT);
            }
            client.stop();
            is_playing_tts = false; // 🟢 解锁麦克风
            Serial.println("✅ TTS Done");
        }
        vTaskDelay(20);
    }
}
