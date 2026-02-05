#ifndef SPEAKER_H
#define SPEAKER_H

#include <Arduino.h>

// 初始化扬声器 (I2S1)
void setupSpeaker();

// 扬声器任务 (接收 TTS 音频并播放)
void speakerTask(void *param);

#endif
