"""TTS via a personal Cloud Run relay, for networks that block ElevenLabs
directly (e.g. content-filtered networks like Netfree). The relay does the
actual ElevenLabs calls outside the filtered network and delivers the
result as a Google Drive link - no audio bytes ever cross the filter.

Same Protocol as the local ElevenLabs provider (see base.py); this class is
a drop-in replacement selected via TTS_PROVIDER=cloudrun.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

CHUNK_CHARS = 800


class CloudRunTTS:
    def __init__(self) -> None:
        self._base_url = os.environ["TTS_SERVICE_URL"].rstrip("/")
        self._secret = os.environ["TTS_SERVICE_SECRET"]

    def _headers(self) -> dict[str, str]:
        return {"x-service-secret": self._secret}

    def _chunk_lines(self, lines: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
        """Group (text, voice_id) lines into chunks under CHUNK_CHARS each,
        never splitting a single line across chunks."""
        chunks: list[list[tuple[str, str]]] = []
        current: list[tuple[str, str]] = []
        current_len = 0
        for text, voice in lines:
            if current and current_len + len(text) > CHUNK_CHARS:
                chunks.append(current)
                current, current_len = [], 0
            current.append((text, voice))
            current_len += len(text)
        if current:
            chunks.append(current)
        return chunks

    def synthesize_dialogue(self, lines: list[tuple[str, str]], path: Path) -> Path:
        """Sends each chunk to /synthesize, then /finalize to get a Drive link.
        `path` is used only for its filename; the audio itself never crosses
        the filtered network, so no local audio file is written at `path`.
        Instead a `path.with_suffix(".url")` sidecar file is written with the
        Drive link - callers on this provider read the link from there.
        (TODO once module 4's shared TTS package lands: give the Protocol a
        proper structured result instead of overloading a bare Path.)
        """
        job_id = path.stem
        for i, chunk in enumerate(self._chunk_lines(lines)):
            resp = httpx.post(
                f"{self._base_url}/synthesize",
                headers=self._headers(),
                json={
                    "job_id": job_id,
                    "chunk_index": i,
                    "lines": [{"text": text, "voice_id": voice} for text, voice in chunk],
                },
                timeout=120,
            )
            resp.raise_for_status()

        resp = httpx.post(
            f"{self._base_url}/finalize",
            headers=self._headers(),
            json={"job_id": job_id, "filename": path.name},
            timeout=120,
        )
        resp.raise_for_status()
        drive_url = resp.json()["url"]

        path.with_suffix(".url").write_text(drive_url, encoding="utf-8")
        return path
