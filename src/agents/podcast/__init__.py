"""Podcast script and audio graphs."""

from __future__ import annotations

import os
from functools import lru_cache

from langgraph.types import Command

from agents.ted.checkpoint import get_saver
from agents.podcast.graph import build_podcast_graph
from agents.podcast.audio_graph import build_audio_graph


@lru_cache
def _graph():
	return build_podcast_graph(checkpointer=get_saver())


def _config(job_id: str) -> dict:
	return {"configurable": {"thread_id": job_id}, "recursion_limit": 40}


def run_start(job_id: str) -> dict:
	result = _graph().invoke({"job_id": job_id}, _config(job_id))
	return result["__interrupt__"][0].value


def run_resume(job_id: str, resume: dict) -> dict:
	return _graph().invoke(Command(resume=resume), _config(job_id))


def get_values(job_id: str) -> dict:
	return _graph().get_state(_config(job_id)).values


@lru_cache
def _audio_graph():
	return build_audio_graph(checkpointer=get_saver())


def _audio_config(job_id: str) -> dict:
	return {"configurable": {"thread_id": f"{job_id}:audio"}, "recursion_limit": 15}


def start_audio(job_id: str, episode_text: str) -> dict:
	paragraphs = [part.strip() for part in episode_text.split("\n\n") if part.strip()]
	host_voice = os.getenv("PODCAST_HOST_VOICE_ID", "host")
	guest_voice = os.getenv("PODCAST_GUEST_VOICE_ID", "guest")
	lines = [
		("Host" if index % 2 == 0 else "Guest", text, host_voice if index % 2 == 0 else guest_voice)
		for index, text in enumerate(paragraphs)
	]
	result = _audio_graph().invoke(
		{"job_id": job_id, "lines": lines}, _audio_config(job_id)
	)
	return result["__interrupt__"][0].value


def resume_audio(job_id: str, resume: dict) -> dict:
	return _audio_graph().invoke(Command(resume=resume), _audio_config(job_id))


def get_audio_values(job_id: str) -> dict:
	return _audio_graph().get_state(_audio_config(job_id)).values