"""Backend services: translate API requests into the LangChain code.

This is the thin layer between the stable API contract and the per-stage implementations.
Source management and notes are product glue (in-memory); chat is powered by the stage-2
agent; Studio artifacts raise ``ComingSoon`` until structured output lands in stage 3.
"""

from __future__ import annotations

import uuid

from api.schemas import (
    ArtifactKind,
    ChatRequest,
    ChatResponse,
    Citation,
    Note,
    SourceDetail,
    SourceInfo,
)
from agents import chat, research
from agents.ted import ted_jobs
from agents import podcast
from core.store import store


class ComingSoon(Exception):
    """Raised for a product capability that is advertised but not wired up yet."""


# -- sources -------------------------------------------------------------------


def _to_info(source) -> SourceInfo:
    return SourceInfo(
        id=source.id, name=source.name, chars=len(source.content), active=source.active
    )


def list_sources() -> list[SourceInfo]:
    return [_to_info(s) for s in store.list()]


def get_source(source_id: str) -> SourceDetail | None:
    source = store.get(source_id)
    if source is None:
        return None
    return SourceDetail(
        id=source.id,
        name=source.name,
        chars=len(source.content),
        active=source.active,
        content=source.content,
    )


def add_source(name: str | None, content: str) -> SourceInfo:
    name = (name or "").strip() or _auto_name(content)
    return _to_info(store.add(name=name, content=content))


def set_source_active(source_id: str, active: bool) -> SourceInfo | None:
    source = store.set_active(source_id, active)
    return _to_info(source) if source else None


def remove_source(source_id: str) -> bool:
    return store.remove(source_id)


def web_search_sources(query: str) -> list[SourceInfo]:
    """Deep-research a topic on the web and add whatever good sources the agent finds."""
    sources = research.research(query)
    return [_to_info(s) for s in sources]


def _auto_name(content: str) -> str:
    first_line = content.strip().splitlines()[0] if content.strip() else "Pasted source"
    first_line = first_line.lstrip("# ").strip()
    return (first_line[:40] or "Pasted source") + ".txt"


# -- chat ----------------------------------------------------------------------


def run_chat(req: ChatRequest) -> ChatResponse:
    """Answer a chat turn with the stage-2 agent, grounded in the active sources."""
    if not store.active_ids():
        return ChatResponse(
            answer="No active sources. Enable at least one source on the left to chat.",
            engine="chat",
        )

    result = chat.answer(req.message, thread_id=req.thread_id or "default")
    citations = [Citation(source=name) for name in result.sources]
    return ChatResponse(answer=result.text, citations=citations, engine="chat")


# -- TED jobs -----------------------------------------------------------------


def start_ted_job(job_id: str | None) -> dict:
    return ted_jobs.start(job_id or uuid.uuid4().hex)


def resume_ted_job(job_id: str, action: str, feedback: str | None) -> dict:
    return ted_jobs.resume(job_id, action, feedback)


def get_ted_job(job_id: str) -> dict:
    return ted_jobs.status(job_id)


def start_podcast_job(job_id: str | None) -> dict:
    actual_id = job_id or uuid.uuid4().hex
    return {"status": "awaiting_approval", "job_id": actual_id, "approval": podcast.run_start(actual_id)}


def resume_podcast_job(job_id: str, action: str, feedback: str | None) -> dict:
    audio_values = podcast.get_audio_values(job_id)
    if audio_values.get("lines"):
        result = podcast.resume_audio(job_id, {"action": action, "feedback": feedback})
        if "__interrupt__" in result:
            return {"status": "awaiting_audio_approval", "job_id": job_id, "approval": result["__interrupt__"][0].value}
        return get_podcast_job(job_id)
    result = podcast.run_resume(job_id, {"action": action, "feedback": feedback})
    if "__interrupt__" in result:
        return {"status": "awaiting_approval", "job_id": job_id, "approval": result["__interrupt__"][0].value}
    script_values = podcast.get_values(job_id)
    approval = podcast.start_audio(job_id, script_values["episode_text"])
    return {"status": "awaiting_audio_approval", "job_id": job_id, "approval": approval}


def get_podcast_job(job_id: str) -> dict:
    values = podcast.get_values(job_id)
    if not values:
        return {"status": "not_found", "job_id": job_id}
    audio_values = podcast.get_audio_values(job_id)
    if audio_values.get("audio_path") or audio_values.get("audio_url"):
        state = "completed"
    elif audio_values.get("lines"):
        state = "awaiting_audio_approval"
    elif values.get("episode_text"):
        state = "awaiting_audio_approval"
    else:
        state = "running"
    return {"status": state, "job_id": job_id, **values, **audio_values}


# -- studio (artifacts) --------------------------------------------------------

ARTIFACTS: list[ArtifactKind] = [
    ArtifactKind(key="infographic", title="Infographic", icon="📊", status="planned"),
    ArtifactKind(key="powerpoint", title="PowerPoint", icon="📑", status="planned"),
    ArtifactKind(key="summary", title="Summary", icon="📄", status="planned"),
    ArtifactKind(key="faq", title="FAQ", icon="❓", status="planned"),
]

_ARTIFACTS_BY_KEY = {a.key: a for a in ARTIFACTS}


def list_artifacts() -> list[ArtifactKind]:
    return ARTIFACTS


def generate_artifact(kind: str, impl: str) -> Note:
    # Artifact generation lands with structured output; until then it's "coming soon".
    artifact = _ARTIFACTS_BY_KEY.get(kind)
    title = artifact.title if artifact else "This artifact"
    raise ComingSoon(f"{title} generation is coming soon.")


# -- notes ---------------------------------------------------------------------

_NOTES: dict[str, Note] = {}


def list_notes() -> list[Note]:
    return list(_NOTES.values())


def add_note(title: str, content: str) -> Note:
    note = Note(id=uuid.uuid4().hex[:8], title=title.strip() or "Untitled note", content=content)
    _NOTES[note.id] = note
    return note


def remove_note(note_id: str) -> bool:
    return _NOTES.pop(note_id, None) is not None
