"""ElevenLabs Text-to-Dialogue via eleven_v3 (the only ElevenLabs model
with Hebrew support).

Whole chunks are sent to the dialogue endpoint; delivery is directed by
v3 audio tags embedded in the text (e.g. [thoughtful] [short pause]).
The dialogue API only supports the `stability` setting.
"""

from __future__ import annotations

import os
from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs.types import DialogueInput, ModelSettingsResponseModel


class ElevenLabsTTS:
    def __init__(self) -> None:
        self._client = ElevenLabs()
        self._model_id = os.getenv("TTS_MODEL", "eleven_v3")
        # 0.0 = Creative, 0.5 = Natural, 1.0 = Robust
        self._stability = float(os.getenv("TTS_STABILITY", "0.35"))

    def synthesize_dialogue(self, lines: list[tuple[str, str]], path: Path) -> Path:
        audio = self._client.text_to_dialogue.convert(
            inputs=[DialogueInput(text=text, voice_id=voice) for text, voice in lines],
            model_id=self._model_id,
            settings=ModelSettingsResponseModel(stability=self._stability),
            output_format="mp3_44100_128",
        )
        with open(path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        return path
