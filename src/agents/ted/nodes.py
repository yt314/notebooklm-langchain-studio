"""LangGraph nodes for the TED talk pipeline: each does one job over TedState."""

from __future__ import annotations

import os
import re
from pathlib import Path

from langgraph.types import interrupt

from agents.ted.models import get_model
from agents.ted.prompts import (
    CRITIQUE_SYSTEM,
    CRITIQUE_USER,
    PLAN_TALK_SYSTEM,
    PLAN_TALK_USER,
    REVISE_SYSTEM,
    REVISE_USER,
    WRITE_TALK_SYSTEM,
    WRITE_TALK_USER,
)
from agents.ted.schemas import CritiqueResult, TalkBrief
from agents.ted.state import (
    HARD_CAP,
    MAX_REVISIONS,
    TARGET_WORDS,
    WORD_MAX,
    WORD_MIN,
    TedState,
)
from agents.ted.tts import get_provider

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


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip())


def count_words(state: TedState) -> dict:
    """Pure code: count the script's words; hard-trim at a sentence boundary
    if the model overshot HARD_CAP. The prompt asks for the budget - this node
    enforces it."""
    script = state["script_he"]
    if len(script.split()) <= HARD_CAP:
        return {"word_count": len(script.split())}

    kept, used = [], 0
    for sentence in _sentences(script):
        n = len(sentence.split())
        if kept and used + n > HARD_CAP:
            break
        kept.append(sentence)
        used += n
    trimmed = " ".join(kept)
    return {"script_he": trimmed, "word_count": len(trimmed.split())}


def critique_script(state: TedState) -> dict:
    """LLM judge: passed/issues. It receives the word count computed in code -
    it does not count by itself."""
    brief = state["brief"]
    llm = get_model("critique").with_structured_output(CritiqueResult)
    result = llm.invoke(
        [
            {
                "role": "system",
                "content": CRITIQUE_SYSTEM.format(word_min=WORD_MIN, word_max=WORD_MAX),
            },
            {
                "role": "user",
                "content": CRITIQUE_USER.format(
                    topic=brief.topic,
                    hook=brief.hook,
                    key_points="\n".join(f"- {p}" for p in brief.key_points),
                    word_count=state["word_count"],
                    script=state["script_he"],
                ),
            },
        ]
    )
    return {"critique": result}


def after_critique(state: TedState) -> str:
    """passed, or out of revision budget -> done. Otherwise revise."""
    if state["critique"].passed or state["revision_count"] >= MAX_REVISIONS:
        return "approval"
    return "revise"


def revise(state: TedState) -> dict:
    """LLM: rewrite the script per the critique issues."""
    critique = state.get("critique")
    issues = (
        "\n".join(f"- {issue}" for issue in critique.issues)
        if critique and critique.issues
        else "אין"
    )

    llm = get_model("writing")
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": REVISE_SYSTEM.format(
                    target_words=TARGET_WORDS, word_min=WORD_MIN, word_max=WORD_MAX
                ),
            },
            {
                "role": "user",
                "content": REVISE_USER.format(
                    script=state["script_he"],
                    word_count=state["word_count"],
                    issues=issues,
                    human_feedback=state.get("human_feedback") or "אין",
                    context=state["context"],
                ),
            },
        ]
    )
    return {
        "script_he": response.text.strip(),
        "revision_count": state["revision_count"] + 1,
        "human_feedback": None,
    }


def approval(state: TedState) -> dict:
    """The human-in-the-loop gate. interrupt() pauses the graph here and the
    checkpointer persists it; the payload below is what the caller shows the
    user. Command(resume={"action": ...}) re-enters this node with the user's
    decision as interrupt()'s return value."""

    # never put side effects before interrupt
    decision = interrupt(
        {
            "topic": state["brief"].topic,
            "script_he": state["script_he"],
            "word_count": state["word_count"],
            "revision_count": state["revision_count"],
            "critique_notes": state["critique"].issues if state.get("critique") else [],
        }
    )

    if decision.get("action") == "revise":
        return {"human_feedback": decision.get("feedback") or "המשתמש/ת ביקש/ה גרסה משופרת."}
    return {"human_feedback": None}


def after_approval(state: TedState) -> str:
    return "revise" if state.get("human_feedback") else "synthesize"


def synthesize_audio(state: TedState) -> dict:
    """Render the approved script once; retrying the node is idempotent."""
    job_id = state["job_id"]
    audio_dir = Path(os.getenv("TED_AUDIO_DIR", "data/ted_audio"))
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = audio_dir / f"{job_id}.mp3"
    sidecar = path.with_suffix(".url")

    if path.exists() or sidecar.exists():
        result = {"audio_path": str(path)}
        if sidecar.exists():
            result["audio_url"] = sidecar.read_text(encoding="utf-8").strip()
        return result

    voice_id = os.environ.get("TED_VOICE_ID")
    if not voice_id:
        raise RuntimeError("TED_VOICE_ID is required to synthesize audio.")

    output = get_provider().synthesize_dialogue([(state["script_he"], voice_id)], path)
    result = {"audio_path": str(output)}
    if sidecar.exists():
        result["audio_url"] = sidecar.read_text(encoding="utf-8").strip()
    return result
