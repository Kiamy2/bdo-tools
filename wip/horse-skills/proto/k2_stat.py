"""K2 check: fast engine (reset in leveling and in the exact cleanup) against the plain-Python simulation
bdo.horses.simulate_plan (reset always on since K3; points_reset=True before), different random numbers, so within noise.
Run from the repo root: python3 -I wip/horse-skills/proto/k2_stat.py"""
import math, sys
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

data = H.load_data()
cases = [("Mythical Diné", "Artisan 7", ("coursier_v2", 15, 9, 0), None),
         ("Mythical Diné", "Artisan 7", ("coursier", 20, 5, 0), None),
         ("Mythical Diné", "Artisan 7", ("at30", 1, 0, 0), None),
         ("T8 example (bdolytics icon horse_71)", "Skilled 1", ("coursier_switch", 8, 15, 11), None),
         ("T8 example (bdolytics icon horse_71)", "Skilled 1", ("coursier_switch", 8, 12, 12), "planned"),
         ("T8 example (bdolytics icon horse_71)", "Skilled 1", ("coursier", 10, 10, 0), "fallback"),
         ("Doom (T9)", "Artisan 8", ("hard", 12, 10, 0), None),
         ("Doom (T9)", "Artisan 8", ("once", 12, 10, 0), None)]
worst = 0
for name, tr, (st, L, cap, T), cp in cases:
    h = H.get_horse(data, name)
    M = h.M(H.training_bonus(tr), 0, 0)
    a = F.Evaluator(h, M, max_budget=20).plans([(st, L, cap, T)], runs=20000, seed=11, tails=True, coupon=cp)[(st, L, cap, T)]
    b = H.simulate_plan(h, M, st, L, cap, 20, runs=6000, seed=12, switch_at=T, coupon=cp)
    zs = []
    for B in (cap, 10, 15, 20):
        if B < cap:
            continue
        for t in range(3):
            x, y = a["tails"][B][t], b["tails"][B][t]
            se = math.sqrt(x * (1 - x) / 20000 + y * (1 - y) / 6000) or 1e-9
            zs.append(abs(x - y) / se)
    z = max(zs)
    worst = max(worst, z)
    print(f"{name[:14]:14s} {tr:10s} {st:15s} {L:2d} {cap:2d} {T:2d} {str(cp):8s} full@20 fast {a['full'][20]:.3f} "
          f"python {b['full'][20]:.3f}  max|z| {z:.2f} over {len(zs)}")
print("RESULT", "OK" if worst < 4 else "DIFF", f"worst z {worst:.2f}")
