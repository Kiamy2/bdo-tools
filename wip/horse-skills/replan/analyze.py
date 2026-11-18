"""Summary of a replan.py results file: fixed vs re-planned, paired over the same horses."""
import collections
import json
import math
import sys

lines = open(sys.argv[1]).read().splitlines()
head = json.loads(lines[0])
rows = [json.loads(x) for x in lines[1:]]
n = len(rows)
print(f"settings: {head['settings']}")
print(f"code: {head['git_commit']} / {head['code_sha256']} | level-1 plan: {head['first_plan_name']} "
      f"(simulated chance {head['first_plan']['chance']:.1%})")
print(f"horses: {n}")


def paired(key):
    d = [r["replan"][key] - r["fixed"][key] for r in rows]
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1)) if n > 1 else float("nan")
    return m, sd / math.sqrt(n)


fx = sum(r["fixed"]["full"] for r in rows) / n
rp = sum(r["replan"]["full"] for r in rows) / n
m, se = paired("full")
print(f"full set: fixed {fx:.1%}, re-planned {rp:.1%}, gain {100 * m:+.1f} points "
      f"(standard error {100 * se:.1f}; 95% range {100 * (m - 1.96 * se):+.1f} to {100 * (m + 1.96 * se):+.1f})")
better = sum(r["replan"]["full"] > r["fixed"]["full"] for r in rows)
worse = sum(r["replan"]["full"] < r["fixed"]["full"] for r in rows)
print(f"  horses where re-planning got the full set and fixed didn't: {better}; the reverse: {worse}; "
      f"same outcome: {n - better - worse}")
for key, label in (("wanted", "travel skills"), ("spent", "coupons spent"), ("skills", "skills at 30")):
    a = sum(r["fixed"][key] for r in rows) / n
    b = sum(r["replan"][key] for r in rows) / n
    m, se = paired(key)
    print(f"{label}: fixed {a:.2f}, re-planned {b:.2f}, difference {m:+.2f} (standard error {se:.2f})")
print("decisions at each checkpoint (re-planned arm):")
by = collections.defaultdict(collections.Counter)
for r in rows:
    for lv, st, sf, cap, ch in r["replan"]["decisions"]:
        kind = "at30" if st == "at30" else f"{st}, start {'now' if sf == lv + 1 else 'later'}"
        by[lv][kind] += 1
for lv in sorted(by):
    tot = sum(by[lv].values())
    print(f"  level {lv}: {tot} decisions: " + ", ".join(f"{k} {v}" for k, v in by[lv].most_common()))
print(f"time: {sum(r['secs'] for r in rows) / 60:.0f} min in total, {sum(r['secs'] for r in rows) / n:.1f}s per horse")
