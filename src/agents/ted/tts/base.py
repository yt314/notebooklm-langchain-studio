"""Provider-agnostic TTS contract the graph depends on."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TTSProvider(Protocol):
    """Provider-agnostic TTS interface the graph depends on."""

    def synthesize_dialogue(self, lines: list[tuple[str, str]], path: Path) -> Path:
        """Render an ordered list of (text, voice_id) lines into one mp3 at `path`."""
        ...
