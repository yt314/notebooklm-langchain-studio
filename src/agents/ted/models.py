"""Role -> model mapping for the TED talk pipeline, so tuning cost/quality is a config change."""

from __future__ import annotations

from functools import lru_cache

from langchain.chat_models import init_chat_model

MODELS = {
    "planning": "google_genai:gemini-flash-latest",  # plan_talk
    "writing": "google_genai:gemini-flash-latest",  # write_talk, revise
    "critique": "google_genai:gemini-flash-latest",  # critique_script
}


@lru_cache
def get_model(role: str):
    return init_chat_model(MODELS[role])
