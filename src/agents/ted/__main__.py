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

graph = build_ted_graph()
final_state = None
config = {
    "recursion_limit": 25,
    "run_name": "ted-talk",
    "metadata": {"job_id": "test"},
}
for mode, chunk in graph.stream(
    {"job_id": "test"},
    config=config,
    stream_mode=["updates", "values"],
):
    if mode == "updates":
        for node in chunk:
            print(f">>> {node} done")
    else:
        final_state = chunk
result = final_state

print(json.dumps(result["brief"].model_dump(), indent=2, ensure_ascii=False))
print("--- script ---")
print(result["script_he"])
print(f"\nword_count (מהקוד): {result['word_count']}")
if result.get("critique"):
    print("critique passed:", result["critique"].passed)
    print("issues:", result["critique"].issues)
print("revisions:", result["revision_count"])
