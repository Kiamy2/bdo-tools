import sys, time; sys.path[:0] = ["/home/claude/bdo-tools", "/home/claude/bdo-tools/wip/horse-skills/proto"]
import numba
from bdo import horses as H
import sim_fast as F
d = H.load_data(); h = H.get_horse(d, "Mythical Diné"); M = h.M(21.7, 0, 0)
t = time.time(); F.simulate_plan_nb(h, M, "hard", 10, 15, 40, runs=10); print(f"numba first call (load cached compile): {time.time()-t:.2f}s")
plans = [("coursier", L, c) for L in (1, 10, 20, 25) for c in (3, 8, 15)] + [("at30", 1, 0), ("once", 15, 8), ("hard", 10, 10)]
def bench(fn, runs, label, reps=1):
    t = time.time()
    for _ in range(reps):
        for st, L, c in plans:
            fn(h, M, st, L, c, 40, runs=runs, seed=1)
    dt = (time.time() - t) / reps / len(plans)
    print(f"{label:34} {1000*dt:9.2f} ms per plan of {runs} horses  ({1e6*dt/runs:7.2f} us/horse)")
    return dt
o = bench(H.simulate_plan, 4000, "current Python")
p = bench(F.simulate_plan_py, 4000, "optimized Python")
numba.set_num_threads(1)
n1 = bench(F.simulate_plan_nb, 4000, "numba, 1 core", reps=5)
numba.set_num_threads(2)
n2 = bench(F.simulate_plan_nb, 4000, "numba, 2 cores", reps=5)
print(f"speed-up vs current: optimized Python x{o/p:.1f}, numba 1 core x{o/n1:.0f}, numba 2 cores x{o/n2:.0f}")
