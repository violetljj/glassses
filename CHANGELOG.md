# Changelog

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-02-04

### 新增
- 🎯 **寻物助手 (Object Finder)**: 语音触发寻物模式，盖格计数器反馈距离
- 🔊 **Qwen-TTS-Realtime**: 集成阿里云实时语音合成，响应更快
- 📚 **Swagger API 文档**: 自动生成的交互式 API 文档 (`/api/docs`)
- 🧪 **自动化测试套件**: pytest 测试覆盖核心模块

### 改进
- ⚡ **MJPEG 流模式**: 相机服务从 HTTP 轮询升级为 MJPEG 流，延迟降低 50%+
- 🔒 **线程安全**: `AppState` 使用 `threading.Lock` 保护所有状态访问
- 📝 **开发者文档**: README 大幅扩展，添加项目结构、测试指南、架构图

### 修复
- 🐛 修复 I2S 冲突导致的 ESP32 音频回声问题
- 🐛 修复 VAD 阈值过低导致的误触发

### 技术债务
- ♻️ 从单体 `server_final.py` 重构为模块化 `services/` 架构

---

## [0.1.0] - 2026-01-15

### 新增
- 初始版本发布
- YOLOv8 实时目标检测
- 多模态 AI 语音助理 (STT + LLM + TTS)
- ESP32-S3 Sense 固件
- Neural Dark UI 前端
