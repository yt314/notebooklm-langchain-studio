"""The live, in-memory corpus of sources plus a semantic vector index over their chunks."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from langchain_cohere import CohereEmbeddings
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from agents.summarize import summarize
from core.sources import chunk_source

EMBEDDING_MODEL = os.getenv("NOTEBOOKLM_EMBEDDING_MODEL", "embed-multilingual-v3.0")


@dataclass
class Source:
    id: str
    name: str
    content: str
    active: bool = True
    summary: str | None = None


class SourceStore:
    """Holds the notebook's sources and a semantic index over their chunks."""

    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.vector_store = InMemoryVectorStore(CohereEmbeddings(model=EMBEDDING_MODEL))
        self._chunk_ids: dict[str, list[str]] = {}

    def add(self, name: str, content: str) -> Source:
        source = Source(
            id=uuid.uuid4().hex[:8], name=name, content=content, summary=summarize(name, content)
        )
        self.sources[source.id] = source
        docs = chunk_source(source.id, source.name, source.content)
        if docs:
            self._chunk_ids[source.id] = self.vector_store.add_documents(docs)
        return source

    def remove(self, source_id: str) -> bool:
        if source_id not in self.sources:
            return False
        del self.sources[source_id]
        chunk_ids = self._chunk_ids.pop(source_id, None)
        if chunk_ids:
            self.vector_store.delete(chunk_ids)
        return True

    def set_active(self, source_id: str, active: bool) -> Source | None:
        source = self.sources.get(source_id)
        if source is None:
            return None
        source.active = active
        return source

    def list(self) -> list[Source]:
        return list(self.sources.values())

    def get(self, source_id: str) -> Source | None:
        return self.sources.get(source_id)

    def active_ids(self) -> set[str]:
        return {s.id for s in self.sources.values() if s.active}

    def search(self, query: str, k: int = 4) -> list[Document]:
        active_ids = self.active_ids()
        if not active_ids:
            return []
        return self.vector_store.similarity_search(
            query, k=k, filter=lambda doc: doc.metadata.get("source_id") in active_ids
        )


store = SourceStore()
