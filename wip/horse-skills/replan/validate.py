import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replan as R
import numpy as np
S = R.Setup(R.SETTINGS); s = R.SETTINGS
t = time.time(); plan, ch = R.decide(S, s, 1, 0, 15, 0, 777); print(f"level-1 decision: {R.NAMES[plan[0]]} from {plan[1]} cap {plan[2]} -> {ch:.1%}  ({time.time()-t:.1f}s, includes compile)")
t = time.time(); plan, ch = R.decide(S, s, 1, 0, 15, 0, 778); print(f"level-1 decision again: {R.NAMES[plan[0]]} from {plan[1]} cap {plan[2]} -> {ch:.1%}  ({time.time()-t:.1f}s)")
# playthrough vs simulator, same plan
N = 20000
t = time.time(); res = [R.play(S, s, plan, 5_000_000 + i) for i in range(N)]
fx = sum(r["full"] for r in res) / N
sim = R.F.simulate_plan_nb(S.horse, S.M, R.NAMES[plan[0]], plan[1], plan[2], 15, runs=200000, seed=9)["full"][15]
print(f"playthrough {fx:.2%} vs simulator {sim:.2%} (se {100*(fx*(1-fx)/N)**.5:.2f} pts)  [{1e6*(time.time()-t)/N:.0f} us/horse]")
for p2 in [(1, 20, 6), (2, 18, 8), (3, 12, 5), (0, 2, 0)]:
    res = [R.play(S, s, p2, 6_000_000 + i) for i in range(N)]
    fx = sum(r["full"] for r in res) / N
    sim = R.F.simulate_plan_nb(S.horse, S.M, R.NAMES[p2[0]], p2[1], p2[2], 15, runs=200000, seed=9)["full"][15]
    print(f"  plan {R.NAMES[p2[0]]} {p2[1]} {p2[2]}: playthrough {fx:.2%} vs simulator {sim:.2%}")
# decision timing from mid-level states
r = R.play(S, s, plan, 123)
for lv, left in [(10, 15), (15, 12), (20, 10), (25, 8)]:
    t = time.time(); p, c = R.decide(S, s, lv, 0b1011, left, 15 - left, 999); print(f"decision at level {lv}, {left} coupons left: {time.time()-t:.2f}s -> {R.NAMES[p[0]]} {p[1]} {p[2]}")
