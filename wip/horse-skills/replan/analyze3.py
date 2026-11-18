"""Summary of a replan3.py results file."""
import collections, json, math, sys
NAMES = {0: "All at 30", 1: "V0", 6: "V2", 12: "V0 until T, then V2"}
L = open(sys.argv[1]).read().splitlines(); head = json.loads(L[0]); rows = [json.loads(x) for x in L[1:]]; n = len(rows)
s = head["settings"]
print(f"{s['horse']} | {s['training']} | {s['coupons']} coupons | level-1 plan {head['first_plan']} ({head['first_plan_chance']:.1%}) | {n} horses")
def paired(k):
    d = [r["replan"][k] - r["fixed"][k] for r in rows]; m = sum(d) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n)
m, se = paired("chance")
print(f"full set: fixed {sum(r['fixed']['chance'] for r in rows)/n:.1%}, re-planned {sum(r['replan']['chance'] for r in rows)/n:.1%}, gain {100*m:+.2f} points (se {100*se:.2f}; 95% range {100*(m-1.96*se):+.2f} to {100*(m+1.96*se):+.2f})")
for k, lab in (("skills", "learned skills at 30"), ("spent_leveling", "coupons spent while leveling")):
    m, se = paired(k); print(f"{lab}: difference {m:+.2f} (se {se:.2f})")
by = collections.defaultdict(collections.Counter)
for r in rows:
    for dec in r["replan"]["decisions"]:
        by[dec[0]][NAMES[dec[1]]] += 1
for lv in sorted(by): print(f"  level {lv}: " + ", ".join(f"{k} {v}" for k, v in by[lv].most_common()))
