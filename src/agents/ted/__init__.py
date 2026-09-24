"""Run interface for the TED talk graph, shared by the dev CLI and the API."""

from __future__ import annotations

from functools import lru_cache

from langgraph.types import Command


@lru_cache
def _graph():
    from agents.ted.checkpoint import get_saver
    from agents.ted.graph import build_ted_graph

    # Compiled once per process; every talk is a separate checkpointed thread.
    return build_ted_graph(checkpointer=get_saver())


def _config(job_id: str) -> dict:
    return {
        "configurable": {"thread_id": job_id},
        "recursion_limit": 25,
        "run_name": "ted-talk",
        "metadata": {"job_id": job_id},
    }


def run_start(job_id: str) -> dict:
    """Run from START until the approval interrupt; returns the interrupt payload."""
    result = _graph().invoke({"job_id": job_id}, _config(job_id))
    return result["__interrupt__"][0].value


def run_resume(job_id: str, resume: dict) -> dict:
    """Resume a paused talk with the user's decision."""
    return _graph().invoke(Command(resume=resume), _config(job_id))


def get_values(job_id: str) -> dict:
    """The talk's current state, read from its checkpoint."""
    return _graph().get_state(_config(job_id)).values
