"""LangGraph nodes for the TED talk pipeline: each does one job over TedState."""

from __future__ import annotations

from agents.ted.models import get_model
from agents.ted.prompts import (
    PLAN_TALK_SYSTEM,
    PLAN_TALK_USER,
    WRITE_TALK_SYSTEM,
    WRITE_TALK_USER,
)
from agents.ted.schemas import TalkBrief
from agents.ted.state import TARGET_WORDS, WORD_MAX, WORD_MIN, TedState

from core.sources import build_sources_overview, format_docs
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


def gather_context(state: TedState) -> dict:
    """No LLM here: retrieve source passages for each key point of the brief."""
    docs, seen = [], set()
    for point in state["brief"].key_points:
        for doc in store.search(point, k=4):
            if doc.page_content not in seen:
                seen.add(doc.page_content)
                docs.append(doc)

    context = format_docs(docs) if docs else "לא נמצאו קטעים רלוונטיים במקורות."
    return {"context": context}


def write_talk(state: TedState) -> dict:
    """LLM: write the full Hebrew script, with the word budget stated in the prompt."""
    brief = state["brief"]
    llm = get_model("writing")
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": WRITE_TALK_SYSTEM.format(
                    target_words=TARGET_WORDS, word_min=WORD_MIN, word_max=WORD_MAX
                ),
            },
            {
                "role": "user",
                "content": WRITE_TALK_USER.format(
                    topic=brief.topic,
                    hook=brief.hook,
                    key_points="\n".join(f"- {p}" for p in brief.key_points),
                    context=state["context"],
                ),
            },
        ]
    )
    return {"script_he": response.text.strip()}
