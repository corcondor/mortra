import json, statistics
from pathlib import Path

root = Path(__file__).resolve().parent
rows = []
for i in range(4):
    d = json.loads((root / f"osrc_{i}.json").read_text())
    rows.extend(d["rows"])

assert len(rows) == 780, len(rows)
keys = [(r["seed"], r["task_id"]) for r in rows]
assert len(set(keys)) == 780
assert len({r["seed"] for r in rows}) == 65
assert sum(bool(r["oracle_source_success"]) for r in rows) == 780

mean_oracle = sum(r["oracle_source_steps"] for r in rows) / len(rows)
mean_generic = sum(r["generic_steps"] for r in rows) / len(rows)
mean_current = sum(r["current_steps"] for r in rows) / len(rows)

assert abs(mean_oracle - 23.694871794871794) < 1e-15
assert abs(mean_generic - 103.25128205128205) < 1e-15
assert abs(mean_current - 102.23205128205129) < 1e-15

agg = json.loads((root / "oracle_source_linear_result_780.json").read_text())
agg_rows = agg["rows"]
assert {(r["seed"], r["task_id"]): r for r in rows} == {(r["seed"], r["task_id"]): r for r in agg_rows}

print("OK")
print("rows:", len(rows))
print("worlds:", len({r['seed'] for r in rows}))
print("oracle_source success:", sum(bool(r['oracle_source_success']) for r in rows))
print("oracle_source mean:", mean_oracle)
print("generic mean:", mean_generic)
print("current mean:", mean_current)
