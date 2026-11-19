"""C15 live: average coupons used to reach the full set, from the user's horse's current state, per plan, with and
without the Skill Change Points reset on a hit. Plain-Python engine (simulate_plan 'needed': total coupons the
full set took, inf if the horse has too few skills), all coupons available (budget large), 4 tickets used on every
empty level-up. Prints, per plan: average coupons, 90th / 99th percentile, chance of the full set within 49.
Usage: python3 -I c15_live.py
"""
import math
import sys
sys.path.insert(0, "/home/claude/bdo-tools")
from bdo import horses as H

d = H.load_data()
h = H.get_horse(d, "Mythical Diné")
res = H.skill_resolver(d)
M = h.M(H.training_bonus("Artisan 8"), 0, 0)
STATE = dict(start_level=4, learned=[res(s) for s in ("Saut haut", "Recul rapide", "Hurlement de cheval")], points=2,
             tickets=4)
CAP = 60
plans = [("at30", 1, 0, 0)]
plans += [(st, L, CAP, 0) for st in ("coursier_v2", "coursier") for L in (5, 10, 15, 20, 25)]
plans += [("coursier_switch", L, CAP, T) for L in (5, 10, 15) for T in (11, 13, 15)]
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
print("plan | no reset: avg coupons, 90% / 99% within, full set within 49 | reset on hit: same")
for p in plans:
    cells = []
    for reset in (False, True):
        r = H.simulate_plan(h, M, p[0], p[1], p[2], 0, runs=RUNS, seed=15, switch_at=p[3], points_reset=reset, **STATE)
        nd = r["needed"]
        fin = [x for x in nd if x != math.inf]
        avg = sum(fin) / len(fin) if fin else math.inf
        q = lambda f: nd[min(len(nd) - 1, int(f * len(nd)))]
        cells.append(f"{avg:5.1f} ({len(fin) / len(nd):.1%} reach it), {q(0.9):.0f} / {q(0.99):.0f}, {sum(x <= 49 for x in nd) / len(nd):.1%}")
    print(f"{H.plan_name(p)} | " + " | ".join(cells), flush=True)
