# -*- coding: utf-8 -*-
"""
A.VISION Services Package

核心服务模块的公开接口导出。
"""

from .state import AppState
from .vision_service import VisionService
from .audio_service import AudioService
from .camera_service import CameraService
from .microphone_service import MicrophoneService
from .voice_assistant import VoiceAssistant

# 可选模块 (需要额外依赖)
try:
    from .omni_service import OmniService
except ImportError:
    OmniService = None

__all__ = [
    "AppState",
    "VisionService",
    "AudioService",
    "CameraService",
    "MicrophoneService",
    "VoiceAssistant",
    "OmniService",
]
