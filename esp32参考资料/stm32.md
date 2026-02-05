Seeed Studio XIAO ESP32S3 Sense 的摄像头使用
tip
本教程的内容仅适用于 Seeed Studio XIAO ESP32S3 Sense。
在本教程中，我们将指导您使用 XIAO ESP32S3 Sense 上的摄像头模块。本教程分为以下几个部分，首先，我们将解释 ESP32 提供的摄像头功能及其特性。其次，我们将从拍照和录像两个维度为您介绍如何使用摄像头，最后，我们将围绕拍照和录像创建一些有趣的项目。
Seeed Studio XIAO ESP32S3 Sense

立即购买 🖱️
入门指南
本教程可能涉及使用 microSD 卡、摄像头、天线等。请准备以下材料，并根据您的项目需求正确安装它们。
天线安装
在 XIAO ESP32S3 正面的左下角，有一个独立的"WiFi/BT 天线连接器"。为了获得更好的 WiFi/蓝牙信号，您需要取出包装内的天线并将其安装在连接器上。
天线的安装有一个小技巧，如果您直接用力按压，您会发现很难按下去，而且手指会疼！正确的天线安装方法是先将天线连接器的一侧放入连接器块中，然后稍微按压另一侧，天线就会安装好。

扩展板安装（适用于 Sense）
安装扩展板非常简单，您只需要将扩展板上的连接器与 XIAO ESP32S3 上的 B2B 连接器对齐，用力按压并听到"咔嗒"声，安装就完成了。

我们现在有一款新的完全兼容 XIAO ESP32S3 Sense 的强大摄像头 OV5640，如果您购买了它，可以更换摄像头来使用。

立即购买 🖱️
如果您需要了解 ov5640 的详细参数信息，可以参考以下图表。

tip
Wiki 中所有关于摄像头的程序都兼容 OV5640 和 OV2640 摄像头。
准备 microSD 卡
XIAO ESP32S3 Sense 支持最大 32GB 的 microSD 卡，所以如果您准备为 XIAO 购买 microSD 卡，请参考此规格。在使用 microSD 卡之前，请将 microSD 卡格式化为 FAT32 格式。

格式化后，您可以将 microSD 卡插入 microSD 卡槽。请注意插入方向，有金手指的一面应朝内。

扩展板的摄像头插槽电路设计
XIAO ESP32S3 Sense 卡槽占用了 ESP32-S3 的 14 个 GPIO，占用的引脚详情如下表所示。
ESP32-S3 GPIO	摄像头	ESP32-S3 GPIO	摄像头
GPIO10	XMCLK	GPIO11	DVP_Y8
GPIO12	DVP_Y7	GPIO13	DVP_PCLK
GPIO14	DVP_Y6	GPIO15	DVP_Y2
GPIO16	DVP_Y5	GPIO17	DVP_Y3
GPIO18	DVP_Y4	GPIO38	DVP_VSYNC
GPIO39	CAM_SCL	GPIO40	CAM_SDA
GPIO47	DVP_HREF	GPIO48	DVP_Y9
开启 PSRAM 选项
ESP32 的 PSRAM 是指 ESP32 芯片上的外部 PSRAM（伪静态随机存取存储器），它提供额外的内存空间来增加 ESP32 系统的可用内存。在 ESP32 系统中，PSRAM 有以下主要用途：
1.
扩展可用 RAM：ESP32 的内置 RAM 有限，特别是对于一些需要大量内存的应用，如图像处理、音频处理等，内置 RAM 可能不够用。通过使用 PSRAM，可以扩展 ESP32 的可用 RAM 来满足这些应用的需求。
2.
3.
加速内存访问：由于 PSRAM 是外部内存，访问速度比内部 RAM 慢，但它可以用作缓存或临时内存来加速内存访问和数据处理。
4.
5.
存储缓冲区：对于需要大缓冲区的应用，如网络缓冲区、音频缓冲区等，PSRAM 可以提供足够的存储空间来避免内存不足的情况。
6.
对于本教程的内容，您需要开启 Arduino IDE 的 PSRAM 功能以确保摄像头正常工作。

摄像头库概述
在我们开始之前，我们建议您阅读本章以了解常见的摄像头功能。这样您就可以使用这些功能来完成自己的项目开发，或者能够更容易地阅读程序。
第一部分：esp_camera.h
1.摄像头初始化的配置结构。
以下是配置的示例，只需根据实际引脚情况填写即可。
static camera_config_t camera_example_config = {
        .pin_pwdn       = PWDN_GPIO_NUM,
        .pin_reset      = RESET_GPIO_NUM,
        .pin_xclk       = XCLK_GPIO_NUM,
        .pin_sccb_sda   = SIOD_GPIO_NUM,
        .pin_sccb_scl   = SIOC_GPIO_NUM,
        .pin_d7         = Y9_GPIO_NUM,
        .pin_d6         = Y8_GPIO_NUM,
        .pin_d5         = Y7_GPIO_NUM,
        .pin_d4         = Y6_GPIO_NUM,
        .pin_d3         = Y5_GPIO_NUM,
        .pin_d2         = Y4_GPIO_NUM,
        .pin_d1         = Y3_GPIO_NUM,
        .pin_d0         = Y2_GPIO_NUM,
        .pin_vsync      = VSYNC_GPIO_NUM,
        .pin_href       = HREF_GPIO_NUM,
        .pin_pclk       = PCLK_GPIO_NUM,

        .xclk_freq_hz   = 20000000, // The clock frequency of the image sensor
        .fb_location = CAMERA_FB_IN_PSRAM; // Set the frame buffer storage location
        .pixel_format   = PIXFORMAT_JPEG, // The pixel format of the image: PIXFORMAT_ + YUV422|GRAYSCALE|RGB565|JPEG
        .frame_size     = FRAMESIZE_UXGA, // The resolution size of the image: FRAMESIZE_ + QVGA|CIF|VGA|SVGA|XGA|SXGA|UXGA
        .jpeg_quality   = 12, // The quality of the JPEG image, ranging from 0 to 63.
        .fb_count       = 2, // The number of frame buffers to use.
        .grab_mode      = CAMERA_GRAB_WHEN_EMPTY //  The image capture mode.
    };
1.初始化摄像头驱动程序。
在按照上述格式配置 camera_example_config 后，我们需要使用此函数来初始化摄像头驱动程序。
esp_err_t esp_camera_init(const camera_config_t* config);

输入参数：摄像头配置参数


输出：成功时返回 ESP_OK

note
目前此函数只能调用一次，没有办法反初始化此模块。
1.获取帧缓冲区的指针。
camera_fb_t* esp_camera_fb_get();
摄像头帧缓冲区的数据结构：
typedef struct {
    uint8_t * buf;              /*!< Pointer to the pixel data */
    size_t len;                 /*!< Length of the buffer in bytes */
    size_t width;               /*!< Width of the buffer in pixels */
    size_t height;              /*!< Height of the buffer in pixels */
    pixformat_t format;         /*!< Format of the pixel data */
    struct timeval timestamp;   /*!< Timestamp since boot of the first DMA buffer of the frame */
} camera_fb_t;
1.返回帧缓冲区以便再次重用。
void esp_camera_fb_return(camera_fb_t * fb);
输入参数：指向帧缓冲区的指针
1.获取指向图像传感器控制结构的指针。
sensor_t * esp_camera_sensor_get();
输出：指向传感器的指针
1.将相机设置保存到非易失性存储器（NVS）。
esp_err_t esp_camera_save_to_nvs(const char *key);
输入参数：相机设置的唯一 nvs 键名
1.从非易失性存储器（NVS）加载相机设置。
esp_err_t esp_camera_load_from_nvs(const char *key);
输入参数：相机设置的唯一 nvs 键名
第二部分：img_converters.h
1.将图像缓冲区转换为 JPEG。
bool fmt2jpg_cb(uint8_t *src, size_t src_len, uint16_t width, uint16_t height, pixformat_t format, uint8_t quality, jpg_out_cb cb, void * arg);

输入参数：

osrc： RGB565、RGB888、YUYV 或 GRAYSCALE 格式的源缓冲区
osrc_len： 源缓冲区的字节长度
owidth： 源图像的像素宽度
oheight： 源图像的像素高度
oformat： 源图像的格式
oquality： 结果图像的 JPEG 质量
ocp： 用于写入输出 JPEG 字节的回调函数
oarg： 传递给回调函数的指针

输出：成功时返回 true

1.将相机帧缓冲区转换为 JPEG。
bool frame2jpg_cb(camera_fb_t * fb, uint8_t quality, jpg_out_cb cb, void * arg);

输入参数：

ofb： 源相机帧缓冲区
oquality： 结果图像的 JPEG 质量
ocp： 用于写入输出 JPEG 字节的回调函数
oarg： 传递给回调函数的指针

输出：成功时返回 true

1.将图像缓冲区转换为 JPEG 缓冲区。
bool fmt2jpg(uint8_t *src, size_t src_len, uint16_t width, uint16_t height, pixformat_t format, uint8_t quality, uint8_t ** out, size_t * out_len);

输入参数：

osrc： RGB565、RGB888、YUYV 或 GRAYSCALE 格式的源缓冲区
osrc_len： 源缓冲区的字节长度
owidth： 源图像的像素宽度
oheight： 源图像的像素高度
oformat： 源图像的格式
oquality： 结果图像的 JPEG 质量
oout： 用于填充结果缓冲区地址的指针。使用完毕后必须释放该指针。
oout_len： 用于填充输出缓冲区长度的指针

输出：成功时返回 true

1.将相机帧缓冲区转换为 JPEG 缓冲区。
bool frame2jpg(camera_fb_t * fb, uint8_t quality, uint8_t ** out, size_t * out_len);

输入参数：

ofb： 源相机帧缓冲区
oquality： 结果图像的 JPEG 质量
oout： 用于填充结果缓冲区地址的指针
oout_len： 用于填充输出缓冲区长度的指针

输出：成功时返回 true

1.将图像缓冲区转换为 BMP 缓冲区。
bool fmt2bmp(uint8_t *src, size_t src_len, uint16_t width, uint16_t height, pixformat_t format, uint8_t ** out, size_t * out_len);

输入参数：

osrc： RGB565、RGB888、YUYV 或 GRAYSCALE 格式的源缓冲区
osrc_len： 源缓冲区的字节长度
owidth： 源图像的像素宽度
oheight： 源图像的像素高度
oformat： 源图像的格式
oquality： 结果图像的 JPEG 质量
oout： 用于填充结果缓冲区地址的指针。
oout_len： 用于填充输出缓冲区长度的指针

输出：成功时返回 true

1.将相机帧缓冲区转换为 BMP 缓冲区。
bool frame2bmp(camera_fb_t * fb, uint8_t ** out, size_t * out_len);

输入参数：

ofb： 源相机帧缓冲区
oquality： 结果图像的 JPEG 质量
ocp： 用于写入输出 JPEG 字节的回调函数
oarg： 传递给回调函数的指针

输出：成功时返回 true

第三部分：app_httpd.cpp
note
这部分库介绍基于创建视频保存终端 -- 基于 WebServer 部分。该库主要用于为 Web 服务器执行图像采集和人脸识别功能。它不直接包含在 ESP 的板载包中。
1.人脸识别功能。
static int run_face_recognition(fb_data_t *fb, std::list<dl::detect::result_t> *results)
输入参数：
ofb：指向表示包含图像数据的帧缓冲区结构的指针。
oresults：指向检测到的人脸结果列表的指针。
1.处理 BMP 图像文件的 HTTP 请求。
static esp_err_t bmp_handler(httpd_req_t *req)
输入参数：指向表示 HTTP 请求的结构的指针。
1.以流式方式编码 JPEG 图像数据。
static size_t jpg_encode_stream(void *arg, size_t index, const void *data, size_t len)
输入参数：
oarg：指向传递给函数的用户定义参数的指针。
oindex：表示图像数据中当前位置的索引值。
odata：指向包含要编码的图像数据的缓冲区的指针。
olen：数据缓冲区的长度。
1.处理从相机捕获和流式传输图像的 HTTP 请求。
static esp_err_t capture_handler(httpd_req_t *req)
输入参数：指向表示 HTTP 请求的结构的指针。
1.处理从相机流式传输视频的 HTTP 请求。
static esp_err_t stream_handler(httpd_req_t *req)
输入参数：指向表示 HTTP 请求的结构的指针。
1.初始化并启动一个通过 HTTP 捕获和流式传输视频的相机服务器。
void startCameraServer()
使用相机拍照
接下来我们从相机的最基本用法开始，例如，我们将首先使用相机来完成图像采集。第一个项目我们将使用 microSD 卡，该程序的主要任务是每分钟获取相机画面，然后将画面保存到 microSD 卡中。
在开始之前，请像我一样安装 microSD 卡和相机。

您可以在下面的链接中找到完整的程序代码和所需的依赖文件。
下载代码
以下是该项目的 Arduino 程序。
#include "esp_camera.h"
#include "FS.h"
#include "SD.h"
#include "SPI.h"

#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM

#include "camera_pins.h"

unsigned long lastCaptureTime = 0; // Last shooting time
int imageCount = 1;                // File Counter
bool camera_sign = false;          // Check camera status
bool sd_sign = false;              // Check sd status

// Save pictures to SD card
void photo_save(const char * fileName) {
  // Take a photo
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Failed to get camera frame buffer");
    return;
  }
  // Save photo to file
  writeFile(SD, fileName, fb->buf, fb->len);

  // Release image buffer
  esp_camera_fb_return(fb);

  Serial.println("Photo saved to file");
}

// SD card write file
void writeFile(fs::FS &fs, const char * path, uint8_t * data, size_t len){
    Serial.printf("Writing file: %s\n", path);

    File file = fs.open(path, FILE_WRITE);
    if(!file){
        Serial.println("Failed to open file for writing");
        return;
    }
    if(file.write(data, len) == len){
        Serial.println("File written");
    } else {
        Serial.println("Write failed");
    }
    file.close();
}

void setup() {
  Serial.begin(115200);
  while(!Serial); // When the serial monitor is turned on, the program starts to execute

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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG; // for streaming
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if(config.pixel_format == PIXFORMAT_JPEG){
    if(psramFound()){
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  camera_sign = true; // Camera initialization check passes

  // Initialize SD card
  if(!SD.begin(21)){
    Serial.println("Card Mount Failed");
    return;
  }
  uint8_t cardType = SD.cardType();

  // Determine if the type of SD card is available
  if(cardType == CARD_NONE){
    Serial.println("No SD card attached");
    return;
  }

  Serial.print("SD Card Type: ");
  if(cardType == CARD_MMC){
    Serial.println("MMC");
  } else if(cardType == CARD_SD){
    Serial.println("SDSC");
  } else if(cardType == CARD_SDHC){
    Serial.println("SDHC");
  } else {
    Serial.println("UNKNOWN");
  }

  sd_sign = true; // sd initialization check passes

  Serial.println("Photos will begin in one minute, please be ready.");
}

void loop() {
  // Camera & SD available, start taking pictures
  if(camera_sign && sd_sign){
    // Get the current time
    unsigned long now = millis();

    //If it has been more than 1 minute since the last shot, take a picture and save it to the SD card
    if ((now - lastCaptureTime) >= 60000) {
      char filename[32];
      sprintf(filename, "/image%d.jpg", imageCount);
      photo_save(filename);
      Serial.printf("Saved picture：%s\n", filename);
      Serial.println("Photos will begin in one minute, please be ready.");
      imageCount++;
      lastCaptureTime = now;
    }
  }
}
note
此程序的编译和上传需要另外两个依赖项，请前往 GitHub 完整下载它们。
请为 XIAO ESP32S3 上传程序，程序上传成功后，请打开串口监视器，调整摄像头对准您想要拍摄的物体，等待一分钟，拍摄的照片将保存到 SD 卡中。接下来，XIAO 将每分钟拍摄一张照片。

取出 microSD 卡，借助读卡器，您可以看到卡内保存的照片。
程序注释
程序开始时导入我们需要使用的摄像头和 SD 卡库，以及我们为 XIAO ESP32S3 定义的一些引脚依赖文件。
然后为了便于阅读，我们依次定义了两个函数，一个是将捕获的图像保存到 SD 卡的函数 photo_save()，另一个是写入文件的函数 writeFile()。
// Save pictures to SD card
void photo_save(const char * fileName) {
  // Take a photo
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Failed to get camera frame buffer");
    return;
  }
  // Save photo to file
  writeFile(SD, fileName, fb->buf, fb->len);

  // Release image buffer
  esp_camera_fb_return(fb);

  Serial.println("Photo saved to file");
}
在将图像保存到 microSD 卡的函数中，完成了两个主要任务。第一个是获取图片，第二个是调用写入文件的函数。
获取图像可以通过 esp_camera_fb_get() 完成，图像信息将保存在指针 fb 中，然后我们可以将 fb 的 buf 写入 SD 卡。
在 Setup() 函数中，程序的很大一部分是配置摄像头引脚和摄像头初始化，我们可以直接默认应用它。如果您对摄像头的像素或质量有要求，可以根据摄像头库概述章节中描述的功能调整其中的值。
在 loop() 函数中最后要做的是控制每分钟拍摄照片，并按照递增数字作为拍摄照片的文件名后缀。
if(camera_sign && sd_sign){
    // Get the current time
    unsigned long now = millis();

    //If it has been more than 1 minute since the last shot, take a picture and save it to the SD card
    if ((now - lastCaptureTime) >= 60000) {
      char filename[32];
      sprintf(filename, "/image%d.jpg", imageCount);
      photo_save(filename);
      Serial.printf("Saved picture：%s\n", filename);
      Serial.println("Photos will begin in one minute, please be ready.");
      imageCount++;
      lastCaptureTime = now;
    }
  }
在执行 loop() 之前，我们配置了两个标志检查 camera_sign 和 sd_sign。这确保了拍摄和保存照片的任务必须在 Setup() 中摄像头和 SD 卡检查成功执行后才能运行。
项目一：制作手持相机
接下来，我们使用上述理论知识创建一个超小型拍照神器。这个项目的最终结果是在 Seeed Studio Round Display for XIAO 上显示实时摄像头画面，当您锁定想要拍摄的物体时，触摸屏幕并拍照记录到 microSD 卡中。
前期准备
在开始这个项目之前，您需要提前准备以下硬件。
Seeed Studio XIAO ESP32S3 Sense	Seeed Studio Round Display for XIAO
	
立即购买 🖱️	立即购买 🖱️
由于此项目将使用 Round Display for XIAO，请在运行此项目的例程之前阅读**显示扩展板的 Wiki 环境配置**的内容，安装必要的库并配置 TFT 环境。
由于 XIAO EPS32S3 Sense 设计时在 SD 卡插槽上连接了三个上拉电阻 R4~R6，而圆形显示屏也有上拉电阻，当两者同时使用时无法读取 SD 卡。为了解决这个问题，我们需要切断 XIAO ESP32S3 Sense 扩展板上的 J3。
tip
但是，我们需要感谢工程师 Mjrovai 提供的同时使用 XIAO ESP32S3 Sense 上 microSD 卡插槽的新方法，这在软件层面也是可能的。我们可以参考**他的方法和程序**。

断开 J3 后，XIAO ESP32S3 Sense 上的 SD 卡插槽将无法正常工作，因此您需要将 microSD 卡插入 Round Display 上的 SD 卡插槽。
接下来，请依次安装 microSD 卡、XIAO ESP32S3 Sense 和 Round Display。

tip
我们建议您先取下摄像头模块，以避免在用刀片切断 J3 连接时刮伤摄像头。
具体操作
您可以在下面的链接中找到完整的程序代码和所需的依赖文件。
下载代码
以下是此项目的 Arduino 程序。
#include <Arduino.h>
#include <TFT_eSPI.h>
#include <SPI.h>
#include "esp_camera.h"
#include "FS.h"
#include "SD.h"
#include "SPI.h"

#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM
#define TOUCH_INT D7

#include "camera_pins.h"

// Width and height of round display
const int camera_width = 240;
const int camera_height = 240;

// File Counter
int imageCount = 1;
bool camera_sign = false;          // Check camera status
bool sd_sign = false;              // Check sd status

TFT_eSPI tft = TFT_eSPI();

// SD card write file
void writeFile(fs::FS &fs, const char * path, uint8_t * data, size_t len){
    Serial.printf("Writing file: %s\n", path);

    File file = fs.open(path, FILE_WRITE);
    if(!file){
        Serial.println("Failed to open file for writing");
        return;
    }
    if(file.write(data, len) == len){
        Serial.println("File written");
    } else {
        Serial.println("Write failed");
    }
    file.close();
}

bool display_is_pressed(void)
{
    if(digitalRead(TOUCH_INT) != LOW) {
        delay(3);
        if(digitalRead(TOUCH_INT) != LOW)
        return false;
    }
    return true;
}

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
//  while(!Serial);

  // Camera pinout
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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
//  config.frame_size = FRAMESIZE_UXGA;
  config.frame_size = FRAMESIZE_240X240;
//  config.pixel_format = PIXFORMAT_JPEG; // for streaming
  config.pixel_format = PIXFORMAT_RGB565;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if(config.pixel_format == PIXFORMAT_JPEG){
    if(psramFound()){
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
  Serial.println("Camera ready");
  camera_sign = true; // Camera initialization check passes

  // Display initialization
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_WHITE);

  // Initialize SD card
  if(!SD.begin(D2)){
    Serial.println("Card Mount Failed");
    return;
  }
  uint8_t cardType = SD.cardType();

  // Determine if the type of SD card is available
  if(cardType == CARD_NONE){
    Serial.println("No SD card attached");
    return;
  }

  Serial.print("SD Card Type: ");
  if(cardType == CARD_MMC){
    Serial.println("MMC");
  } else if(cardType == CARD_SD){
    Serial.println("SDSC");
  } else if(cardType == CARD_SDHC){
    Serial.println("SDHC");
  } else {
    Serial.println("UNKNOWN");
  }

  sd_sign = true; // sd initialization check passes

}

void loop() {
  if( sd_sign && camera_sign){

    // Take a photo
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Failed to get camera frame buffer");
      return;
    }

    if(display_is_pressed()){
      Serial.println("display is touched");
      char filename[32];
      sprintf(filename, "/image%d.jpg", imageCount);
      // Save photo to file
      writeFile(SD, filename, fb->buf, fb->len);
      Serial.printf("Saved picture：%s\n", filename);
      imageCount++;
    }

    // Decode JPEG images
    uint8_t* buf = fb->buf;
    uint32_t len = fb->len;
    tft.startWrite();
    tft.setAddrWindow(0, 0, camera_width, camera_height);
    tft.pushColors(buf, len);
    tft.endWrite();

    // Release image buffer
    esp_camera_fb_return(fb);

    delay(10);
  }
}
将程序上传到 XIAO ESP32S3 Sense，如果上传成功后屏幕没有亮起，您可能需要点击 XIAO 上的 Reset 按钮，然后您将看到监控画面实时显示在圆形显示屏上。点击屏幕上的任意位置，图像将被记录并保存在 microSD 卡中。

程序注释
摄像头和 microSD 卡的配置是之前的内容，所以我们在这里不再重复。关于 microSD 卡的使用，您可以参考 XIAO ESP32S3 Sense 文件系统 Wiki 来学习如何使用它。
// Take a photo
camera_fb_t *fb = esp_camera_fb_get();
if (!fb) {
  Serial.println("Failed to get camera frame buffer");
  return;
}

...

// Release image buffer
esp_camera_fb_return(fb);

delay(10);
上述程序是调用摄像头的基本代码块，分为三个部分：屏幕捕获、异常退出和释放照片缓冲区。
if(display_is_pressed()){
  Serial.println("display is touched");
  char filename[32];
  sprintf(filename, "/image%d.jpg", imageCount);
  // Save photo to file
  writeFile(SD, filename, fb->buf, fb->len);
  Serial.printf("Saved picture：%s\n", filename);
  imageCount++;
}
上述程序用于检查屏幕是否被触摸。如果是，代码将捕获的图像保存到 microSD 卡上的文件中。
// Decode JPEG images
uint8_t* buf = fb->buf;
uint32_t len = fb->len;
tft.startWrite();
tft.setAddrWindow(0, 0, camera_width, camera_height);
tft.pushColors(buf, len);
tft.endWrite();
这部分代码在屏幕上显示捕获的图像。它首先从 camera_fb_t 结构中检索图像缓冲区及其长度。然后，它设置屏幕以接收图像数据，并使用 pushColors() 函数在屏幕上显示图像。
录制短视频并保存到 microSD 卡
note
我们不建议在 MCU 上进行视频编码导出，因为目前支持的编码库资源太少，操作非常复杂和繁琐。
此示例不涉及视频编码，导出的视频是每帧 AVI 的 MJPG 合成，因此视频录制可能不是特别好和令人满意。本教程的目的是为您提供录制短视频的简单方法和思路，我们欢迎有更好解决方案的合作伙伴向我们提交 PR。
在前面的章节中，我们掌握了如何使用摄像头捕获图像。我们知道单个图像拼接在一起可以制作动态视频画面。基于这个理论，本章的项目将指导您如何编写程序每 1 分钟录制 10 秒视频并将其保存在 microSD 卡中。
您可以在下面的链接中找到完整的程序代码和所需的依赖文件。
下载代码
以下是此项目的 Arduino 程序。
#include "esp_camera.h"
#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include "esp_timer.h"

#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM

#include "camera_pins.h"

const int SD_PIN_CS = 21;

File videoFile;
bool camera_sign = false;
bool sd_sign = false;
unsigned long lastCaptureTime = 0;
unsigned long captureDuration = 10000; // 10 seconds
int imageCount = 0;

void setup() {
  Serial.begin(115200);
  while(!Serial);

  // Initialize the camera
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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_SVGA;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  camera_sign = true;

  // Initialize the SD card
  if (!SD.begin(SD_PIN_CS)) {
    Serial.println("SD card initialization failed!");
    return;
  }

  uint8_t cardType = SD.cardType();

  // Determine if the type of SD card is available
  if(cardType == CARD_NONE){
    Serial.println("No SD card attached");
    return;
  }

  Serial.print("SD Card Type: ");
  if(cardType == CARD_MMC){
    Serial.println("MMC");
  } else if(cardType == CARD_SD){
    Serial.println("SDSC");
  } else if(cardType == CARD_SDHC){
    Serial.println("SDHC");
  } else {
    Serial.println("UNKNOWN");
  }

  sd_sign = true;

  Serial.println("Video will begin in one minute, please be ready.");
}

void loop() {
  // Camera & SD available, start taking video
  if (camera_sign && sd_sign) {
    // Get the current time
    unsigned long now = millis();

    //If it has been more than 1 minute since the last video capture, start capturing a new video
    if ((now - lastCaptureTime) >= 60000) {
      char filename[32];
      sprintf(filename, "/video%d.avi", imageCount);
      videoFile = SD.open(filename, FILE_WRITE);
      if (!videoFile) {
        Serial.println("Error opening video file!");
        return;
      }
      Serial.printf("Recording video：%s\n", filename);
      lastCaptureTime = now;

      // Start capturing video frames
      while ((millis() - lastCaptureTime) < captureDuration) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
          Serial.println("Error getting framebuffer!");
          break;
        }
        videoFile.write(fb->buf, fb->len);
        esp_camera_fb_return(fb);
      }

      // Close the video file
      videoFile.close();
      Serial.printf("Video saved: %s\n", filename);
      imageCount++;

      Serial.println("Video will begin in one minute, please be ready.");

      // Wait for the remaining time of the minute
      delay(60000 - (millis() - lastCaptureTime));
    }
  }
}
将代码上传到 XIAO ESP32S3 Sense，打开串口监视器，此时请调整摄像头位置对准您要录制的对象，一分钟后，XIAO 上的橙色 LED 将开始闪烁，录制将开始并保存到 microSD 卡。

note
由于程序不涉及编码和帧率等设置，如果录制画面的每一帧都没有变化，视频可能只能打开一秒钟。
程序注释
录制视频过程中的核心和关键是在连续的 10 秒时间内持续获取照片流并将其连续写入 microSD 卡。
// Start capturing video frames
while ((millis() - lastCaptureTime) < captureDuration) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Error getting framebuffer!");
    break;
  }
  videoFile.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}
在此基础上，我们在外层嵌套一层 1 分钟等待判断，以确保视频每 1 分钟开始一次。
//If it has been more than 1 minute since the last video capture, start capturing a new video
if ((now - lastCaptureTime) >= 60000) {

  ...

  delay(60000 - (millis() - lastCaptureTime));
}
项目二：视频流
在本教程的最后，让我们展示一个视频流项目。该项目允许您在 XIAO ESP32S3 Sense 创建的网页上看到实时视频流，您可以通过设置一些参数来改变屏幕的显示。
您可以在下面的链接中找到完整的程序代码和所需的依赖文件。
如果您在 Arduino 上使用 2.0.x 版本的 esp32 boards 包。请下载：
下载代码
如果您在 Arduino 上使用 3.0.x 版本的 esp32 开发板包，请下载：
下载代码
以下是此项目的 Arduino 程序。
#include "esp_camera.h"
#include <WiFi.h>

#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM

#include "camera_pins.h"

// ===========================
// Enter your WiFi credentials
// ===========================
const char* ssid = "**********";
const char* password = "**********";

void startCameraServer();
void setupLedFlash(int pin);

void setup() {
  Serial.begin(115200);
  while(!Serial);
  Serial.setDebugOutput(true);
  Serial.println();

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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG; // for streaming
  //config.pixel_format = PIXFORMAT_RGB565; // for face detection/recognition
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if(config.pixel_format == PIXFORMAT_JPEG){
    if(psramFound()){
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  // initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1); // flip it back
    s->set_brightness(s, 1); // up the brightness just a bit
    s->set_saturation(s, -2); // lower the saturation
  }
  // drop down frame size for higher initial frame rate
  if(config.pixel_format == PIXFORMAT_JPEG){
    s->set_framesize(s, FRAMESIZE_QVGA);
  }

// Setup LED FLash if LED pin is defined in camera_pins.h
#if defined(LED_GPIO_NUM)
  setupLedFlash(LED_GPIO_NUM);
#endif

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");

  startCameraServer();

  Serial.print("Camera Ready! Use 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("' to connect");
}

void loop() {
  // Do nothing. Everything is done in another task by the web server
  delay(10000);
}
在上传程序之前，您需要将代码中的 WiFi 名称和密码更改为您自己的。上传程序后，如果 XIAO ESP32C3 成功连接到您的 WiFi，它的 IP 地址将被打印出来。
caution
XIAO ESP32S3 如果您长时间执行此项目，请注意散热，XIAO 会变得非常热，请小心烫伤！

tip
如上图所示，如果您打开调试信息输出，那么您可能会在串口监视器中看到一些芯片内核的调试信息被打印出来。例如 [0;31mE (2947) MFN: Partition Not found[0m，请不要担心，这不会影响程序的运行。
请打开您的浏览器，我们推荐 Edge 或 Google Chrome，输入该 IP 地址，您将看到视频的配置页面。
note
请注意，您使用浏览器的设备需要与 XIAO 在同一局域网内。
配置好您想要设置的视频流规格后，点击左侧工具栏底部的 Start Stream，您将看到摄像头的实时画面。

幸运的是，ESP32 官方也在程序中添加了人脸识别功能。您可以通过打开人脸识别的按钮开关来体验该功能，但画质会降低。
tip
出于性能考虑，当您打开人脸识别开关时，画面质量不能高于 CIF，否则网页会弹出错误。

哦，我的大脸被圈起来了。

OV5640 自动对焦
硬件准备
OV5640 Camera for XIAO ESP32S3 Sense

立即购买 🖱️
软件准备
方法 1
特别感谢 @Eric 提供的开源代码
下载库文件
代码示例
#include "esp_camera.h"
#include <WiFi.h>
#include "ESP32_OV5640_AF.h"

#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM

#include "camera_pins.h"

const char* ssid = "";
const char* password = "";

void startCameraServer();
void setupLedFlash(int pin);
OV5640 ov5640 = OV5640();

void setup() {
  Serial.begin(115200);
  while(!Serial);
  Serial.setDebugOutput(true);
  Serial.println();

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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG; // for streaming
  //config.pixel_format = PIXFORMAT_RGB565; // for face detection/recognition
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if(config.pixel_format == PIXFORMAT_JPEG){
    if(psramFound()){
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  ov5640.start(s);

    if (ov5640.focusInit() == 0) {
    Serial.println("OV5640_Focus_Init Successful!");
  }

  if (ov5640.autoFocusMode() == 0) {
    Serial.println("OV5640_Auto_Focus Successful!");
  }

// Setup LED FLash if LED pin is defined in camera_pins.h
#if defined(LED_GPIO_NUM)
  setupLedFlash(LED_GPIO_NUM);
#endif

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");

  startCameraServer();

  Serial.print("Camera Ready! Use 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("' to connect");
}

void loop() {
  uint8_t rc = ov5640.getFWStatus();
  Serial.printf("FW_STATUS = 0x%x\n", rc);

  if (rc == -1) {
    Serial.println("Check your OV5640");
  } else if (rc == FW_STATUS_S_FOCUSED) {
    Serial.println("Focused!");
  } else if (rc == FW_STATUS_S_FOCUSING) {
    Serial.println("Focusing!");
  }
}
结果图表
tip
分辨率需要在 1280*1024 以上才能看到对焦效果，对焦时屏幕会卡顿，需要等待一段时间。

方法 2
tip
分辨率需要在 1600*1200 以上才能看到对焦效果，对焦时屏幕会卡顿，需要等待一段时间。
下载以下 zip 文件并添加到 Arduino
[ZIP] OV5640 Auto
tip
方法 1 和方法 2 的库中的 OV5640 不能同时存在
#include "esp_camera.h"
#include <WiFi.h>
#include "ESP32_OV5640_AF.h"

#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM

#include "camera_pins.h"

const char *ssid = "";
const char *password = "";

void startCameraServer();
void setupLedFlash(int pin);
OV5640 ov5640 = OV5640();

void setup() {
  Serial.begin(115200);

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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 10;
  config.fb_count = 2;

  if(psramFound()){
    config.jpeg_quality = 10;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    // Limit the frame size when PSRAM is not available
    config.frame_size = FRAMESIZE_SVGA;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  // auto focus
#if 1
  sensor_t* sensor = esp_camera_sensor_get();
  int ret = 0;
  ov5640.start(sensor);

  if (ov5640.focusInit() == 0) {
      Serial.println("OV5640_Focus_Init Successful!");
  } else {
      Serial.println("OV5640_Focus_Init Failed!");
  }

  ret = ov5640.autoFocusMode(false);
  if (ret == 0) {
    Serial.println("OV5640_Auto_Focus Successful!");
  } else {
    Serial.printf("OV5640_Auto_Focus Failed! - [%d]\n", ret);
  }
#endif

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  startCameraServer();

  Serial.printf("Camera Ready! Use 'http://%s' to connect\n", WiFi.localIP().toString().c_str());
}

void loop() {
  if (Serial.available()) {
    sensor_t* sensor = esp_camera_sensor_get();
    int ret = 0;

    switch (Serial.read()) {
      case 'b':
        ret = sensor->set_reg(sensor, 0x3022, 0xff, 0x03);
        Serial.printf("begin to auto focus - %d\n", ret);
        break;
      case 's':
        ret = sensor->set_reg(sensor, 0x3022, 0xff, 0x06);
        Serial.printf("focus stop here - %d\n", ret);
        break;
    }
  }

  uint8_t rc = ov5640.getFWStatus();
  Serial.printf("FW_STATUS = 0x%x\n", rc);

  if (rc == -1) {
    Serial.println("Check your OV5640");
  } else if (rc == FW_STATUS_S_FOCUSED) {
    Serial.println("Focused!");
  } else if (rc == FW_STATUS_S_FOCUSING) {
    Serial.println("Focusing!");
  } else {
  }

  delay(1000);
}
tip
推荐使用模式 1，因为它比模式 2 具有更明显的对焦效果，并提供更清晰的图像。
故障排除
Q1：当 XIAO ESP32S3 Sense 和圆形显示屏一起使用时，我必须切断 J3 引脚吗？可以使用哪个 SD 卡插槽？
A：原则上，当 XIAO ESP32S3 Sense 与圆形显示屏一起使用时，需要切断 J3 引脚才能使用 microSD 卡。原因是两个扩展板的电路设计中都有上拉电阻，所以理论上，如果两个上拉电阻同时工作，那么 SD 卡插槽将无法正常工作。会出现 SD 卡挂载失败的错误信息。由于圆形显示屏上的上拉电阻无法屏蔽，您需要切断 sense 扩展板上的 J3，以确保两者一起使用时只有一个上拉电阻工作。这也决定了当两者一起使用时，只有圆形显示屏上的 SD 卡插槽是有效的。
但是，我们需要感谢工程师 Mjrovai 提供的同时使用 XIAO ESP32S3 Sense 上 microSD 卡插槽的新方法，这在软件层面也是可能的。我们可以参考**他的方法和程序**。













Seeed Studio XIAO ESP32S3 麦克风的使用
在本教程中，我们将为您介绍如何使用 XIAO ESP32S3 Sense 扩展板的麦克风。首先是 I2S 引脚的基本使用，我们将通过使用 I2S 和麦克风获取当前环境的响度，并在串口波形图中显示。然后我们将解释如何录制声音并将录制的声音保存到 SD 卡中。
Seeed Studio XIAO ESP32S3 Sense

立即购买 🖱️
caution
本教程的所有内容仅适用于 XIAO ESP32S3 Sense。
入门指南
在开始教程内容之前，您可能需要提前准备以下硬件和软件。
扩展板的安装（适用于 Sense）
安装扩展板非常简单，您只需要将扩展板上的连接器与 XIAO ESP32S3 上的 B2B 连接器对齐，用力按下并听到"咔嗒"声，安装就完成了。

准备 microSD 卡
在进行保存录音的项目时，您可能需要一张 MicroSD 卡。
XIAO ESP32S3 Sense 支持最大 32GB 的 microSD 卡，所以如果您准备为 XIAO 购买 microSD 卡，请参考此规格。在使用 microSD 卡之前，请将 microSD 卡格式化为 FAT32 格式。

格式化后，您可以将 microSD 卡插入 microSD 卡槽。请注意插入方向，有金手指的一面应朝内。

了解引脚
引脚编号	功能描述
GPIO 41	PDM 麦克风 DATA
GPIO 42	PDM 麦克风 CLK
声音响度检测
对于第一个项目案例，让我们检测环境中的噪音，并使用 Arduino IDE 的串口波形图显示麦克风检测到的环境响度。
以下是完整的示例程序。
tip
检查并确认您使用的 esp32 版本，以下示例适用于 2.0.x，下面的示例适用于 3.0.x 及更高版本
#include <I2S.h>

void setup() {
  // Open serial communications and wait for port to open:
  // A baud rate of 115200 is used instead of 9600 for a faster data rate
  // on non-native USB ports
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // start I2S at 16 kHz with 16-bits per sample
  I2S.setAllPins(-1, 42, 41, -1, -1);
  if (!I2S.begin(PDM_MONO_MODE, 16000, 16)) {
    Serial.println("Failed to initialize I2S!");
    while (1); // do nothing
  }
}

void loop() {
  // read a sample
  int sample = I2S.read();

  if (sample && sample != -1 && sample != 1) {
    Serial.println(sample);
  }
}
tip
上面的示例仅与 esp32 的 2.0.x 兼容，如果您使用的是最新版本（例如 3.0.x），请使用下面的示例
#include <ESP_I2S.h>
I2SClass I2S;

void setup() {
  // Open serial communications and wait for port to open:
  // A baud rate of 115200 is used instead of 9600 for a faster data rate
  // on non-native USB ports
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // setup 42 PDM clock and 41 PDM data pins
  I2S.setPinsPdmRx(42, 41);

  // start I2S at 16 kHz with 16-bits per sample
  if (!I2S.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    Serial.println("Failed to initialize I2S!");
    while (1); // do nothing
  }
}

void loop() {
  // read a sample
  int sample = I2S.read();

  if (sample && sample != -1 && sample != 1) {
    Serial.println(sample);
  }
}
为 XIAO ESP32S3 Sense 上传此程序并打开 串口绘图器，您将看到声音的响度变化曲线。

程序注释
在程序开始时，我们需要首先导入 I2S 库以便使用麦克风引脚。
#include <I2S.h>
在 I2S 对象上调用 setAllPins() 函数来配置用于 I2S 接口的引脚。该函数接受五个整数参数，分别表示连接到 I2S 接口的位时钟、字选择、数据输入、数据输出和通道选择线的 GPIO 引脚。
I2S.setAllPins(-1, 42, 41, -1, -1);
在这个特定的代码中，-1 值表示相应的引脚未使用，而 42 和 41 值分别表示连接到字选择和数据输入线的 GPIO 引脚。数据输出和通道选择线在此配置中未使用，设置为 -1。
if (!I2S.begin(PDM_MONO_MODE, 16000, 16)) {
    Serial.println("Failed to initialize I2S!");
    while (1); // do nothing
}
在 I2S 对象上调用 begin() 函数，使用指定参数初始化 I2S 接口：PDM_MONO_MODE、16000 Hz 采样率和 16 位 分辨率。
tip
需要注意的是，对于当前的 ESP32-S3 芯片，我们只能使用 PDM_MONO_MODE，采样位宽只能是 16bit。只有采样率可以修改，但经过测试，16kHz 的采样率相对稳定。
int sample = I2S.read();

if (sample && sample != -1 && sample != 1) {
    Serial.println(sample);
}
在 I2S 对象上调用 read() 函数从 I2S 接口读取单个音频样本。if 语句检查 sample 变量的值。如果样本值不是 0、-1 或 1，则被认为是有效的音频样本，if 块内的代码将被执行。在这种情况下，使用 Serial.println() 函数将样本值打印到串口控制台。
将录制的声音保存到 microSD 卡
在下一个项目中，我们将指导您如何结合 microSD 卡的功能，将录制的声音保存到 microSD 卡中。对于这个项目，请提前准备 microSD 卡并将其格式化为 FAT32 格式。
如果这是您第一次在 XIAO ESP32S3 上使用 microSD 卡，您可以阅读文件系统 Wiki 内容来了解 microSD 卡的安装和准备。
以下是此项目的 Arduino 程序。
tip
检查并确认您使用的 esp32 版本，以下示例适用于 2.0.x，下面的示例适用于 3.0.x 及更高版本
/* 
 * WAV Recorder for Seeed XIAO ESP32S3 Sense 
*/

#include <I2S.h>
#include "FS.h"
#include "SD.h"
#include "SPI.h"

// make changes as needed
#define RECORD_TIME   20  // seconds, The maximum value is 240
#define WAV_FILE_NAME "arduino_rec"

// do not change for best
#define SAMPLE_RATE 16000U
#define SAMPLE_BITS 16
#define WAV_HEADER_SIZE 44
#define VOLUME_GAIN 2

void setup() {
  Serial.begin(115200);
  while (!Serial) ;
  I2S.setAllPins(-1, 42, 41, -1, -1);
  if (!I2S.begin(PDM_MONO_MODE, SAMPLE_RATE, SAMPLE_BITS)) {
    Serial.println("Failed to initialize I2S!");
    while (1) ;
  }
  if(!SD.begin(21)){
    Serial.println("Failed to mount SD Card!");
    while (1) ;
  }
  record_wav();
}

void loop() {
  delay(1000);
  Serial.printf(".");
}

void record_wav()
{
  uint32_t sample_size = 0;
  uint32_t record_size = (SAMPLE_RATE * SAMPLE_BITS / 8) * RECORD_TIME;
  uint8_t *rec_buffer = NULL;
  Serial.printf("Ready to start recording ...\n");

  File file = SD.open("/"WAV_FILE_NAME".wav", FILE_WRITE);
  // Write the header to the WAV file
  uint8_t wav_header[WAV_HEADER_SIZE];
  generate_wav_header(wav_header, record_size, SAMPLE_RATE);
  file.write(wav_header, WAV_HEADER_SIZE);

  // PSRAM malloc for recording
  rec_buffer = (uint8_t *)ps_malloc(record_size);
  if (rec_buffer == NULL) {
    Serial.printf("malloc failed!\n");
    while(1) ;
  }
  Serial.printf("Buffer: %d bytes\n", ESP.getPsramSize() - ESP.getFreePsram());

  // Start recording
  esp_i2s::i2s_read(esp_i2s::I2S_NUM_0, rec_buffer, record_size, &sample_size, portMAX_DELAY);
  if (sample_size == 0) {
    Serial.printf("Record Failed!\n");
  } else {
    Serial.printf("Record %d bytes\n", sample_size);
  }

  // Increase volume
  for (uint32_t i = 0; i < sample_size; i += SAMPLE_BITS/8) {
    (*(uint16_t *)(rec_buffer+i)) <<= VOLUME_GAIN;
  }

  // Write data to the WAV file
  Serial.printf("Writing to the file ...\n");
  if (file.write(rec_buffer, record_size) != record_size)
    Serial.printf("Write file Failed!\n");

  free(rec_buffer);
  file.close();
  Serial.printf("The recording is over.\n");
}

void generate_wav_header(uint8_t *wav_header, uint32_t wav_size, uint32_t sample_rate)
{
  // See this for reference: http://soundfile.sapp.org/doc/WaveFormat/
  uint32_t file_size = wav_size + WAV_HEADER_SIZE - 8;
  uint32_t byte_rate = SAMPLE_RATE * SAMPLE_BITS / 8;
  const uint8_t set_wav_header[] = {
    'R', 'I', 'F', 'F', // ChunkID
    file_size, file_size >> 8, file_size >> 16, file_size >> 24, // ChunkSize
    'W', 'A', 'V', 'E', // Format
    'f', 'm', 't', ' ', // Subchunk1ID
    0x10, 0x00, 0x00, 0x00, // Subchunk1Size (16 for PCM)
    0x01, 0x00, // AudioFormat (1 for PCM)
    0x01, 0x00, // NumChannels (1 channel)
    sample_rate, sample_rate >> 8, sample_rate >> 16, sample_rate >> 24, // SampleRate
    byte_rate, byte_rate >> 8, byte_rate >> 16, byte_rate >> 24, // ByteRate
    0x02, 0x00, // BlockAlign
    0x10, 0x00, // BitsPerSample (16 bits)
    'd', 'a', 't', 'a', // Subchunk2ID
    wav_size, wav_size >> 8, wav_size >> 16, wav_size >> 24, // Subchunk2Size
  };
  memcpy(wav_header, set_wav_header, sizeof(set_wav_header));
}
tip
上面的示例仅与 esp32 的 2.0.x 版本兼容，如果您使用的是最新版本（例如 3.0.x），请使用下面的示例
#include "ESP_I2S.h"
#include "FS.h"
#include "SD.h"

void setup() {
  // Create an instance of the I2SClass
  I2SClass i2s;

  // Create variables to store the audio data
  uint8_t *wav_buffer;
  size_t wav_size;

  // Initialize the serial port
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  Serial.println("Initializing I2S bus...");

  // Set up the pins used for audio input
  i2s.setPinsPdmRx(42, 41);

  // start I2S at 16 kHz with 16-bits per sample
  if (!i2s.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    Serial.println("Failed to initialize I2S!");
    while (1); // do nothing
  }

  Serial.println("I2S bus initialized.");
  Serial.println("Initializing SD card...");

  // Set up the pins used for SD card access
  if(!SD.begin(21)){
    Serial.println("Failed to mount SD Card!");
    while (1) ;
  }
  Serial.println("SD card initialized.");
  Serial.println("Recording 20 seconds of audio data...");

  // Record 20 seconds of audio data
  wav_buffer = i2s.recordWAV(20, &wav_size);

  // Create a file on the SD card
  File file = SD.open("/arduinor_rec.wav", FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file for writing!");
    return;
  }

  Serial.println("Writing audio data to file...");

  // Write the audio data to the file
  if (file.write(wav_buffer, wav_size) != wav_size) {
    Serial.println("Failed to write audio data to file!");
    return;
  }

  // Close the file
  file.close();

  Serial.println("Application complete.");
}

void loop() {
  delay(1000);
  Serial.printf(".");
}
要执行此示例，我们需要使用 ESP-32 芯片的 PSRAM 功能，因此请在上传之前将其打开。

此程序仅在用户打开串口监视器后执行一次，录制 20 秒并将录制文件保存到 microSD 卡中，文件名为"arduino_rec.wav"。
当串口监视器每 1 秒输出一个"."时，程序执行完成，您可以借助读卡器播放录制的声音文件。

tip
要播放从 XIAO ESP32S3 录制的音频，您可能需要使用支持 WAV 格式的音频播放器。
程序注释
在这个程序中，我们为录音功能编写了两个函数，一个是 record_wav()，另一个是 generate_wav_header()。

record_wav()：录音函数。在此函数中，程序使用 I2S 接口从麦克风读取音频数据，并将其作为 WAV 音频文件存储到 SD 卡中。

a. 初始化变量。程序定义了一个用于存储录制数据的缓冲区 rec_buffer，并设置录制时间 RECORD_TIME。

b. 打开 WAV 文件。程序使用 SD.open() 函数打开一个 WAV 音频文件，并将其文件名定义为 WAV_FILE_NAME。

c. 写入 WAV 文件头。程序使用 generate_wav_header() 函数生成 WAV 音频文件的头信息，并将其写入打开的 WAV 文件中。

d. 分配内存并开始录制。程序使用 ps_malloc() 函数在 ESP32S3 的 PSRAM 中分配一块内存用于存储录制数据，并使用 esp_i2s::i2s_read() 函数从麦克风读取音频数据。读取的数据存储在 rec_buffer 缓冲区中。

e. 增加音量。程序使用由 VOLUME_GAIN 常量定义的增益值来增加录制数据的音量。

f. 将录制数据写入 WAV 文件。程序使用 file.write() 函数将录制数据写入打开的 WAV 文件中。

g. 释放缓冲区内存并关闭 WAV 文件。程序使用 free() 函数释放 rec_buffer 缓冲区的内存，并使用 file.close() 函数关闭打开的 WAV 文件。


generate_wav_header(uint8_t *wav_header, uint32_t wav_size, uint32_t sample_rate)：用于生成 WAV 文件头信息的函数。在此函数中，程序根据 WAV 文件的规范生成包含 WAV 文件头信息的字节数组。

a. 定义 WAV 文件头信息的常量。程序定义了一个包含 WAV 文件头信息的字节数组 set_wav_header，并定义了 WAV 文件规范的常量，包括 NUM_CHANNELS、BITS_PER_SAMPLE、WAV_HEADER_SIZE 和 SUB_CHUNK_SIZE。

b. 设置 WAV 文件头信息。程序使用步骤 a 中定义的常量设置 WAV 文件头信息，并根据 WAV 文件规范计算一些字段的值，包括 AUDIO_FORMAT、BYTE_RATE、BLOCK_ALIGN、SAMPLES_PER_CHANNEL 和 CHUNK_SIZE。计算出的值存储在 set_wav_header 字节数组中。

c. 复制 WAV 文件头信息。程序将存储在 set_wav_header 中的头信息复制到字节数组 wav_header 中。

故障排除
为什么无法播放录制的音频文件？
如果您遇到无法播放的情况，请检查串口监视器打印的调试信息中是否有关于读写卡的错误消息。如果有，请更换 microSD 卡或检查卡与扩展板连接是否松动或不稳定。如果卡没有问题，那么音频文件应该有大小，如果录制有问题，可能会显示录制的音频文件大小只有 0KB。
例如，在下图中，读写卡存在问题。

如果卡没有问题且录制相当成功。那么您需要检查软件是否支持 WAV 格式的音频播放。我们建议使用专门的音乐播放软件来播放音频，尽量不要使用视频播放器来播放。经过实际测试，有许多视频播放器（虽然它们支持 WAV 格式）无法播放。
