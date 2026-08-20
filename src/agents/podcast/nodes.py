"""LangGraph nodes for the podcast script pipeline."""

from __future__ import annotations

from langgraph.types import interrupt

from agents.podcast.models import get_model
from agents.podcast.prompts import (
    CRITIQUE_SYSTEM,
    CRITIQUE_USER,
    PLAN_SYSTEM,
    PLAN_USER,
    REVISE_SYSTEM,
    REVISE_USER,
    SEGMENT_SYSTEM,
    SEGMENT_USER,
)
from agents.podcast.schemas import EpisodeCritique, EpisodePlan
from agents.podcast.state import MAX_REVISIONS, TOTAL_WORDS, PodcastState, clamp_words, segment_budget
from core.sources import build_sources_overview, format_docs
from core.store import store


def plan_episode(state: PodcastState) -> dict:
    overview = build_sources_overview(store)
    if not overview.strip():
        raise ValueError("No active sources to plan a podcast from.")
    result = get_model("planning").with_structured_output(EpisodePlan).invoke(
        [
            {"role": "system", "content": PLAN_SYSTEM},
            {"role": "user", "content": PLAN_USER.format(overview=overview)},
        ]
    )
    return {"plan": result, "research": {}, "segments": [], "revision_count": 0}


def fan_out_segments(state: PodcastState):
    from langgraph.types import Send

    return [Send("research_segment", {"segment": segment}) for segment in state["plan"].segments]


def research_segment(state: PodcastState) -> dict:
    docs = []
    seen = set()
    for doc in store.search(state["segment"].goal, k=4):
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            docs.append(doc)
    return {"research": {state["segment"].index: format_docs(docs)}}


def write_segment(state: PodcastState) -> dict:
    segment = state["segment"]
    budget = segment_budget(TOTAL_WORDS, len(state["plan"].segments))
    result = get_model("writing").invoke(
        [
            {"role": "system", "content": SEGMENT_SYSTEM.format(budget=budget)},
            {
                "role": "user",
                "content": SEGMENT_USER.format(
                    episode_title=state["plan"].title,
                    goal=segment.goal,
                    research=state.get("research", {}).get(segment.index, "אין חומר נוסף."),
                ),
            },
        ]
    )
    return {"segments": [{"index": segment.index, "text": clamp_words(result.text.strip(), budget)}]}


def assemble_episode(state: PodcastState) -> dict:
    ordered = sorted(state.get("segments", []), key=lambda item: item["index"])
    episode = "\n\n".join(item["text"] for item in ordered)
    return {"episode_text": episode, "word_count": len(episode.split())}


def critique_episode(state: PodcastState) -> dict:
    plan = "\n".join(f"{s.index}. {s.title}: {s.goal}" for s in state["plan"].segments)
    result = get_model("critique").with_structured_output(EpisodeCritique).invoke(
        [
            {"role": "system", "content": CRITIQUE_SYSTEM},
            {
                "role": "user",
                "content": CRITIQUE_USER.format(
                    plan=plan,
                    word_count=state["word_count"],
                    episode=state["episode_text"],
                ),
            },
        ]
    )
    return {"critique": result}


def after_critique(state: PodcastState) -> str:
    if state["critique"].passed or state["revision_count"] >= MAX_REVISIONS:
        return "approval"
    return "revise"


def revise_episode(state: PodcastState) -> dict:
    critique = state.get("critique")
    issues = "\n".join(f"- {issue}" for issue in (critique.issues if critique else []))
    result = get_model("writing").invoke(
        [
            {"role": "system", "content": REVISE_SYSTEM},
            {
                "role": "user",
                "content": REVISE_USER.format(
                    episode=state["episode_text"],
                    issues=issues or "אין",
                    feedback=state.get("human_feedback") or "אין",
                ),
            },
        ]
    )
    revised = clamp_words(result.text.strip(), int(TOTAL_WORDS * 1.15))
    return {
        "episode_text": revised,
        "word_count": len(revised.split()),
        "revision_count": state["revision_count"] + 1,
        "human_feedback": None,
    }


def approval(state: PodcastState) -> dict:
    decision = interrupt(
        {
            "episode_text": state["episode_text"],
            "word_count": state["word_count"],
            "revision_count": state["revision_count"],
        }
    )
    if decision.get("action") == "revise":
        return {"human_feedback": decision.get("feedback") or "נא לשפר את הפרק."}
    return {"human_feedback": None}


def after_approval(state: PodcastState) -> str:
    return "revise" if state.get("human_feedback") else "done"