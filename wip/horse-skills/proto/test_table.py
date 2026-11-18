import sys, os, time, random, math
sys.path[:0] = ["/home/claude/bdo-tools", os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from bdo import horses as H
import sim_fast as F
import table_nb as T
from cleanup_exact import Cleanup
d = H.load_data()
h = H.get_horse(d, "Mythical Diné"); M = h.M(21.7, 0, 0)
ev = T.Evaluator(h, M, max_budget=40)
t = time.time(); ev.plan("coursier", 20, 5, runs=50); print(f"compile/first call {time.time()-t:.1f}s")
# 1. leveling identical to sim_fast (skills at 30, same seeds)
for st, L, cap in [("coursier", 20, 5), ("once", 18, 8), ("hard", 12, 5), ("at30", 1, 0)]:
    A = ev.args
    S, base, pts = T._many30(4000, 3, A["w"], A["n"], A["W"], A["M"], T.STRAT[st], L, cap, 0, 1, A["lmask"], A["wmask"],
                             A["fod"], A["order"], A["rare"], 0.25, 0, 30)
    ref = F.simulate_plan_nb(h, M, st, L, cap, 40, runs=4000, seed=3)
    same = sorted(bin(int(x)).count("1") for x in S) == [int(x) for x in ref["skill_counts"]]
    print(f"1. {st:8} leveling identical to sim_fast: {same}")
# 2. table values equal the Python table
A = ev.args
S, base, pts = T._many30(300, 5, A["w"], A["n"], A["W"], A["M"], 0, 1, 0, 0, 1, A["lmask"], A["wmask"], A["fod"], A["order"], A["rare"], 0.25, 0, 30)
starts = list({(int(s), int(p)) for s, p in zip(S, pts)})
CL = Cleanup(list(A["w"]), int(A["wmask"]), list(A["order"]), ev.rare)
Gpy = CL.table(starts, 40)
ev.table.ensure([(s << 7) | p for s, p in starts])
mx = 0
for (s, p) in starts:
    r = ev.table.rows_of([(s << 7) | p])[0]
    mx = max(mx, float(np.abs(ev.table.G[r] - Gpy[(s, p)]).max()))
print(f"2. largest difference numba vs Python table over {len(starts)} start states: {mx:.2e}")
# 3. plan results vs simulated 'rarest' cleanup from the same level-30 states
for st, L, cap in [("coursier", 20, 5), ("at30", 1, 0), ("coursier_v1", 18, 8), ("coursier_v2", 18, 8)]:
    N = 4000
    res = ev.plan(st, L, cap, runs=N, seed=9)
    S, base, pts = T._many30(N, 9, A["w"], A["n"], A["W"], A["M"], T.STRAT[st], L, cap if st != "at30" else 0, 0, 1, A["lmask"], A["wmask"], A["fod"], A["order"], A["rare"], 0.25, 0, 30)
    rng = random.Random(1); Tn = []
    for s, b, p in zip(S, base, pts):
        x = CL.mc_needed(int(s), int(p), rng, "rarest")
        Tn.append(math.inf if x is None else b + x)
    mc = [sum(t <= B for t in Tn) / N for B in (10, 15, 20, 30)]
    print(f"3. {st:12} exact {' '.join(f'{100*res['full'][B]:5.1f}%' for B in (10,15,20,30))} | simulated {' '.join(f'{100*x:5.1f}%' for x in mc)}")
print(f"table size: {ev.table.rows} entries")
