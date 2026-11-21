"""Summary of a replan_save.py results file. Usage: python3 -I analyze_save.py FILE"""
import collections, json, math, sys
L = open(sys.argv[1]).read().splitlines()
head, rows = json.loads(L[0]), [json.loads(x) for x in L[1:]]
n, s = len(rows), head["settings"]
print(f"{s['horse']} | {s['training']} | target {s['target']:.0%} | cap {s['coupon_cap']} coupons | {n} horses")
print(f"level-1 choice: {head['first_plan']}, budget {head['first_budget']}: {head['first_chance']:.1%}, "
      f"{head['first_used']:.2f} coupons expected")
mean = lambda xs: sum(xs) / len(xs)
def se(xs):
    m = mean(xs); return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))
lab = {"a": "a fixed (level-1 plan and budget)", "b": "b fixed plan, cleanup up to the cap", "c": "c re-planned"}
for k in "abc":
    f, u = [r[k][0] for r in rows], [r[k][1] for r in rows]
    us = sorted(u)
    print(f"{lab[k]:38s} full set {100 * mean(f):5.1f}% (se {100 * se(f):.1f}) | coupons used {mean(u):5.2f} "
          f"(se {se(u):.2f}; median {us[n // 2]:.1f}, 90th pct {us[int(0.9 * n)]:.1f})")
for x, y in (("c", "a"), ("c", "b")):
    df = [r[x][0] - r[y][0] for r in rows]; du = [r[x][1] - r[y][1] for r in rows]
    print(f"{x} - {y}: full set {100 * mean(df):+.2f} points (se {100 * se(df):.2f}), coupons {mean(du):+.2f} "
          f"(se {se(du):.2f})")
last = [r["decisions"][-1] for r in rows if r["decisions"]]
print(f"c: last decision's predicted chance {100 * mean([d[-2] for d in last]):.1f}% over {len(last)} horses "
      f"(realized {100 * mean([r['c'][0] for r in rows if r['decisions']]):.1f}%)")
by = collections.defaultdict(list)
for r in rows:
    for d in r["decisions"]:
        by[d[0]].append(d)
for lv in sorted(by):
    ds = by[lv]
    cnt = collections.Counter(d[1] for d in ds)
    print(f"  level {lv}: {len(ds)} decisions, budget from now avg {mean([d[5] for d in ds]):.1f} "
          f"(min {min(d[5] for d in ds)}, max {max(d[5] for d in ds)}), target missed {sum(d[6] < s['target'] - 1e-9 for d in ds)}"
          f" | " + ", ".join(f"{k} {v}" for k, v in cnt.most_common()))
