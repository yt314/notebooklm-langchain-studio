"""Dev runner: uv run python -m agents.ted notes.txt article.md"""

from netfree_unstrict_ssl import unstrict_ssl

unstrict_ssl()

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents.ted import get_values, run_resume, run_start
from core.store import store

for arg in sys.argv[1:]:
    path = Path(arg)
    store.add(name=path.name, content=path.read_text(encoding="utf-8"))
    print(f"loaded source: {path.name}")

payload = run_start("test")

while True:
    print("--- script ---")
    print(payload["script_he"])
    print(f"\n({payload['word_count']} מילים, {payload['revision_count']} תיקונים)")
    if payload["critique_notes"]:
        print("הערות המבקר:", payload["critique_notes"])

    answer = input("לאשר? (y = אישור / כל טקסט אחר = משוב לשינוי): ").strip()
    if answer.lower() == "y":
        resume = {"action": "approve"}
    else:
        resume = {"action": "revise", "feedback": answer}

    result = run_resume("test", resume)
    if "__interrupt__" not in result:
        break
    payload = result["__interrupt__"][0].value

print("ההרצאה אושרה — הגרף הסתיים.")
final = get_values("test")
print(f"word_count (מהקוד): {final['word_count']}")
print("revisions:", final["revision_count"])
