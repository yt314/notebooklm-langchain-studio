"""Shared state and deterministic word-budget helpers for podcasts."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from agents.podcast.schemas import EpisodeCritique, EpisodePlan, SegmentPlan

TOTAL_WORDS = 1200
MIN_SEGMENT_WORDS = 120
MAX_SEGMENT_WORDS = 500
MAX_REVISIONS = 2


def merge_research(left: dict[int, str], right: dict[int, str]) -> dict[int, str]:
    return {**left, **right}


class PodcastState(TypedDict, total=False):
    job_id: str
    plan: EpisodePlan
    segment: SegmentPlan
    research: Annotated[dict[int, str], merge_research]
    segments: Annotated[list[dict], operator.add]
    episode_text: str
    word_count: int
    critique: EpisodeCritique | None
    revision_count: int
    human_feedback: str | None


def segment_budget(total_words: int, segment_count: int) -> int:
    if segment_count <= 0:
        raise ValueError("segment_count must be positive")
    raw = total_words // segment_count
    return max(MIN_SEGMENT_WORDS, min(MAX_SEGMENT_WORDS, raw))


def clamp_words(text: str, maximum: int) -> str:
    words = text.split()
    return " ".join(words[:maximum])