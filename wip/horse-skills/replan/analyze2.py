"""Summary of a replan2.py results file (scores = exact chance of the full set at level 30)."""
import collections, json, math, sys
L = open(sys.argv[1]).read().splitlines(); head = json.loads(L[0]); rows = [json.loads(x) for x in L[1:]]; n = len(rows)
print(f"settings: {head['settings']}\ncode {head['git_commit']} / {head['code_sha256']} | level-1 plan {head['first_plan']} ({head['first_plan_chance']:.1%})\nhorses: {n}")
def paired(f):
    d = [f(r["replan"]) - f(r["fixed"]) for r in rows]; m = sum(d) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n)
fx = sum(r["fixed"]["chance"] for r in rows) / n; rp = sum(r["replan"]["chance"] for r in rows) / n
m, se = paired(lambda x: x["chance"])
print(f"full set: fixed {fx:.1%}, re-planned {rp:.1%}, gain {100*m:+.2f} points (standard error {100*se:.2f}; 95% range {100*(m-1.96*se):+.2f} to {100*(m+1.96*se):+.2f})")
for k, lab in (("wanted_at30", "travel skills at 30 (before cleanup)"), ("skills", "skills at 30"), ("spent_leveling", "coupons spent while leveling")):
    m, se = paired(lambda x: x[k]); print(f"{lab}: fixed {sum(r['fixed'][k] for r in rows)/n:.2f}, re-planned {sum(r['replan'][k] for r in rows)/n:.2f}, difference {m:+.2f} (se {se:.2f})")
print("re-planned decisions by checkpoint:")
by = collections.defaultdict(collections.Counter)
for r in rows:
    for lv, st, sf, cap, ch in r["replan"]["decisions"]:
        by[lv][st if st == "at30" else f"{st} start {'next level' if sf == lv + 1 else 'later'}"] += 1
for lv in sorted(by): print(f"  level {lv}: " + ", ".join(f"{k} {v}" for k, v in by[lv].most_common()))
print(f"time {sum(r['secs'] for r in rows)/60:.1f} min")
