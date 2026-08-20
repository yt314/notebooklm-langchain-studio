"""The TED talk graph's shared state and length-budget constants."""

from __future__ import annotations

from typing import TypedDict

from agents.ted.schemas import CritiqueResult, TalkBrief

# Length budget, enforced in code (not left to the model's judgment).
# ~140 spoken Hebrew words per minute -> ~700 words for a 5-minute talk.
TARGET_WORDS = 700
WORD_MIN = 600
WORD_MAX = 800
HARD_CAP = int(TARGET_WORDS * 1.15)  # scripts longer than this get trimmed in code
MAX_REVISIONS = 2  # bounds the critique -> revise loop


class TedState(TypedDict, total=False):
    # input
    job_id: str
    # planning
    brief: TalkBrief
    context: str  # passages retrieved from the sources for each key point
    # writing + quality loop
    script_he: str
    word_count: int
    critique: CritiqueResult | None
    revision_count: int
