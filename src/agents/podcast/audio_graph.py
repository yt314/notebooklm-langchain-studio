"""Independent multi-speaker audio graph for approved podcast scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.ted.tts import get_provider


class PodcastAudioState(TypedDict, total=False):
    job_id: str
    lines: list[tuple[str, str, str]]
    audio_path: str
    audio_url: str | None
    human_feedback: str | None
    audio_status: str


def prepare_audio(state: PodcastAudioState) -> dict:
    if not state.get("lines"):
        raise ValueError("Podcast audio requires at least one dialogue line.")
    return {}


def approval(state: PodcastAudioState) -> dict:
    decision = interrupt({"job_id": state["job_id"], "lines": state["lines"]})
    if decision.get("action") == "revise":
        return {"human_feedback": decision.get("feedback") or "נא לתקן את הדיאלוג."}
    return {"human_feedback": None}


def after_approval(state: PodcastAudioState) -> str:
    return "revise" if state.get("human_feedback") else "synthesize"


def revise_audio(state: PodcastAudioState) -> dict:
    return {"audio_status": "needs_script_revision", "human_feedback": None}


def synthesize_multi_speaker(state: PodcastAudioState) -> dict:
    output_dir = Path(os.getenv("PODCAST_AUDIO_DIR", "data/podcast_audio"))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{state['job_id']}.mp3"
    sidecar = path.with_suffix(".url")
    if path.exists() or sidecar.exists():
        result = {"audio_path": str(path)}
        if sidecar.exists():
            result["audio_url"] = sidecar.read_text(encoding="utf-8").strip()
        return result
    output = get_provider().synthesize_dialogue(
        [(text, voice_id) for _, text, voice_id in state["lines"]], path
    )
    result = {"audio_path": str(output)}
    if sidecar.exists():
        result["audio_url"] = sidecar.read_text(encoding="utf-8").strip()
    return result


def build_audio_graph(checkpointer=None):
    builder = StateGraph(PodcastAudioState)
    builder.add_node("prepare_audio", prepare_audio)
    builder.add_node("approval", approval)
    builder.add_node("revise_audio", revise_audio)
    builder.add_node("synthesize_multi_speaker", synthesize_multi_speaker)
    builder.add_edge(START, "prepare_audio")
    builder.add_edge("prepare_audio", "approval")
    builder.add_conditional_edges(
        "approval", after_approval, {"revise": "revise_audio", "synthesize": "synthesize_multi_speaker"}
    )
    builder.add_edge("revise_audio", END)
    builder.add_edge("synthesize_multi_speaker", END)
    return builder.compile(checkpointer=checkpointer)