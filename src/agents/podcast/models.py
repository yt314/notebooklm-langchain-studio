"""Model selection for podcast stages."""

from functools import lru_cache

from langchain.chat_models import init_chat_model


@lru_cache
def get_model(role: str):
    return init_chat_model("google_genai:gemini-2.5-flash")