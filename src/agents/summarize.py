"""One-shot source summarization, used to build a cheap overview for content-generation agents."""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model

MODEL = os.getenv("NOTEBOOKLM_SUMMARY_MODEL", "google_genai:gemini-2.5-flash")

SUMMARY_PROMPT = (
    "Summarize the following source in 5-10 concise sentences, in the same "
    "language as the source. Focus on what the document is about and its "
    "key points.\n\nTitle: {name}\n\nContent:\n{content}"
)


def summarize(name: str, content: str) -> str | None:
    """Best-effort summary; a failure here must not block adding the source."""
    try:
        llm = init_chat_model(MODEL)
        result = llm.invoke(SUMMARY_PROMPT.format(name=name, content=content))
        return result.text.strip()
    except Exception:
        return None
