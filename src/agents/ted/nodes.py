"""LangGraph nodes for the TED talk pipeline: each does one job over TedState."""

from __future__ import annotations

from agents.ted.models import get_model
from agents.ted.prompts import PLAN_TALK_SYSTEM, PLAN_TALK_USER
from agents.ted.schemas import TalkBrief
from agents.ted.state import TedState

from core.sources import build_sources_overview
from core.store import store


def plan_talk(state: TedState) -> dict:
    """LLM: plan the talk (topic, hook, 3 key points) from the source summaries."""
    overview = build_sources_overview(store)
    if not overview.strip():
        raise ValueError("No active sources to plan a talk from. Enable at least one source first.")

    llm = get_model("planning").with_structured_output(TalkBrief)
    brief = llm.invoke(
        [
            {"role": "system", "content": PLAN_TALK_SYSTEM},
            {"role": "user", "content": PLAN_TALK_USER.format(source_overview=overview)},
        ]
    )
    return {"brief": brief, "revision_count": 0}
