"""The conversational chat agent: RAG-grounded Q&A over the notebook's sources, with memory."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from core.sources import format_docs
from core.store import SourceStore, store


@dataclass
class Answer:
    text: str
    sources: list[str] = field(default_factory=list)


MODEL = os.getenv("NOTEBOOKLM_CHAT_MODEL", "google_genai:gemini-2.5-flash")

SYSTEM_PROMPT = """You are the assistant for a notebook of source documents.

You have three tools for working with the user's sources:
- search_sources: semantic search over the currently active sources. Use this first for any
  question that could be answered from the documents.
- list_sources: lists the sources in the notebook (id, name, active state). Use this when the
  user asks what documents are available, or to find an id before calling get_source.
- get_source: fetches the full raw text of one source by id. Use this only when the user
  explicitly wants a whole document, or search_sources snippets aren't enough context.

Ground your answers in the retrieved passages and mention which source(s) they came from. If
nothing relevant turns up in the sources, say so plainly instead of guessing.
"""

# Shared across calls so conversation history actually persists per thread_id.
_checkpointer = InMemorySaver()

_SOURCE_TAG = re.compile(r"\(source: ([^)]+)\)")


def _make_tools(store: SourceStore):
    @tool
    def search_sources(query: str) -> str:
        """Find passages in the active sources that are relevant to a query."""
        docs = store.search(query=query)
        if not docs:
            return "No relevant documents found in the active sources"
        return format_docs(docs)

    @tool
    def list_sources() -> str:
        """List the sources in the notebook, with their id, name, and whether they're active."""
        sources = store.list()
        if not sources:
            return "No sources have been added yet."
        return "\n".join(f"- id={s.id} name={s.name!r} active={s.active}" for s in sources)

    @tool
    def get_source(source_id: str) -> str:
        """Fetch the full text of one source by its id (use list_sources to find ids)."""
        source = store.get(source_id)
        if source is None:
            return f"No source found with id {source_id!r}."
        return f"(source: {source.name})\n{source.content}"

    return [search_sources, list_sources, get_source]


def _cited_sources(messages) -> list[str]:
    """Names of sources returned by search_sources calls this turn, in first-seen order."""
    seen: dict[str, None] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.name == "search_sources":
            for name in _SOURCE_TAG.findall(str(msg.content)):
                seen.setdefault(name, None)
    return list(seen)


def answer(question: str, thread_id: str) -> Answer:
    agent = create_agent(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=_checkpointer,
        tools=_make_tools(store),
    )

    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}, config=config
    )

    text = result["messages"][-1].text
    sources = _cited_sources(result["messages"])
    return Answer(text=text, sources=sources)
