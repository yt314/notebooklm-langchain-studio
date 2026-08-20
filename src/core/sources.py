"""Turning raw source text into indexable chunks, and formatting retrieved chunks for an LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

if TYPE_CHECKING:
    from core.store import SourceStore

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def chunk_source(source_id: str, name: str, content: str) -> list[Document]:
    """Split a source's text into overlapping chunks, each tagged with its source metadata."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return [
        Document(page_content=chunk, metadata={"source_id": source_id, "source": name})
        for chunk in splitter.split_text(content)
    ]


def format_docs(docs: list[Document]) -> str:
    """Render retrieved chunks as a numbered, source-labeled string for the LLM's context."""
    parts = [
        f"[{i}] (source: {doc.metadata.get('source', 'unknown')})\n{doc.page_content}"
        for i, doc in enumerate(docs, start=1)
    ]
    return "\n\n".join(parts)


def build_sources_overview(store: "SourceStore") -> str:
    """A cheap per-source overview (summary, falling back to a raw excerpt) for planning agents."""
    parts = []
    for source in store.list():
        if not source.active:
            continue
        summary = source.summary or source.content[:500]
        parts.append(f"### {source.name}\n{summary}")
    return "\n\n".join(parts)
