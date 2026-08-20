import os
from functools import lru_cache

from .base import TTSProvider


@lru_cache
def get_provider() -> TTSProvider:
    name = os.getenv("TTS_PROVIDER", "elevenlabs")
    if name == "elevenlabs":
        from .elevenlabs import ElevenLabsTTS

        return ElevenLabsTTS()
    if name == "cloudrun":
        from .cloudrun import CloudRunTTS

        return CloudRunTTS()
    raise ValueError(f"Unknown TTS provider: {name}")
