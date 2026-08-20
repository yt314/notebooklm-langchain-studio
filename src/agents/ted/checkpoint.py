"""Singleton SqliteSaver for the TED graph.

The checkpoints live in their own SQLite file, so a talk paused at the
approval interrupt survives a server restart - that is the whole point of
using SqliteSaver here instead of InMemorySaver.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

DATA_DIR = Path("data")
TED_CHECKPOINTS_PATH = DATA_DIR / "ted_checkpoints.sqlite"

_lock = threading.Lock()
_saver = None


def get_saver():
    global _saver
    with _lock:
        if _saver is None:
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            from langgraph.checkpoint.sqlite import SqliteSaver

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False: FastAPI runs sync endpoints in a threadpool.
            conn = sqlite3.connect(TED_CHECKPOINTS_PATH, check_same_thread=False)
            # Our own Pydantic models live inside the checkpointed state, so the
            # serializer must be told explicitly that they are safe to load.
            serde = JsonPlusSerializer(
                allowed_msgpack_modules=[
                    ("agents.ted.schemas", "TalkBrief"),
                    ("agents.ted.schemas", "CritiqueResult"),
                    ("agents.podcast.schemas", "EpisodePlan"),
                    ("agents.podcast.schemas", "EpisodeCritique"),
                    ("agents.podcast.schemas", "SegmentPlan"),
                ]
            )
            _saver = SqliteSaver(conn, serde=serde)
        return _saver
