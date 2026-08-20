"""Small job facade around the checkpointed TED graph."""

from __future__ import annotations

from agents.ted import get_values, run_resume, run_start


def start(job_id: str) -> dict:
    return {"status": "awaiting_approval", "job_id": job_id, "approval": run_start(job_id)}


def resume(job_id: str, action: str, feedback: str | None = None) -> dict:
    if action not in {"approve", "revise"}:
        raise ValueError("action must be 'approve' or 'revise'")
    result = run_resume(job_id, {"action": action, "feedback": feedback})
    if "__interrupt__" in result:
        return {"status": "awaiting_approval", "approval": result["__interrupt__"][0].value}
    return status(job_id)


def status(job_id: str) -> dict:
    values = get_values(job_id)
    if not values:
        return {"status": "not_found", "job_id": job_id}
    if values.get("audio_path") or values.get("audio_url"):
        state = "completed"
    elif values.get("script_he"):
        state = "awaiting_approval"
    else:
        state = "running"
    return {"status": state, "job_id": job_id, **values}