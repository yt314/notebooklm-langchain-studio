"""Dev runner: uv run python -m agents.ted notes.txt article.md"""

from netfree_unstrict_ssl import unstrict_ssl

unstrict_ssl()

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents.ted.graph import build_ted_graph
from core.store import store

for arg in sys.argv[1:]:
    path = Path(arg)
    store.add(name=path.name, content=path.read_text(encoding="utf-8"))
    print(f"loaded source: {path.name}")

result = build_ted_graph().invoke({"job_id": "test"})

print(json.dumps(result["brief"].model_dump(), indent=2, ensure_ascii=False))
print("--- script ---")
print(result["script_he"])
print(f"\n({len(result['script_he'].split())} מילים)")
