import sys, math, time; sys.path[:0] = ["/home/claude/bdo-tools", "/home/claude/bdo-tools/wip/horse-skills/proto"]
from bdo import horses as H
import sim_fast as F
d = H.load_data()
CASES = [  # (label, horse, training bonus, gear, brand, strategy, swap_from, cap, extra kwargs)
    ("Diné A7 at30", "Mythical Diné", 21.7, 0, 0, "at30", 1, 0, {}),
    ("Diné A7 coursier L15 c12", "Mythical Diné", 21.7, 0, 0, "coursier", 15, 12, {}),
    ("Diné A7 both once L20 c8", "Mythical Diné", 21.7, 1, 1, "once", 20, 8, {}),
    ("Diné A7 once L1 c10", "Mythical Diné", 21.7, 0, 0, "once", 1, 10, {}),
    ("Doom A7 hard L10 c15", "Doom (T9)", 21.7, 0, 0, "hard", 10, 15, {}),
    ("T8 P10 coursier L5 c20", "T8 example (bdolytics icon horse_71)", 16.8, 0, 0, "coursier", 5, 20, {}),
    ("Diné Guru natural", "Mythical Diné", 100, 0, 0, "natural", 1, 0, {}),
    ("user Diné coursier L14 c8", "Mythical Diné", 21.7, 0, 0, "coursier", 14, 8,
     dict(start_level=2, learned=["High Jump"], points=1, tickets=4)),
]
def cmp(a, b, n):
    """largest z-score between two results (proportions and averages), for budgets 0..40"""
    zs = []
    for B in range(41):
        if a["full"][B] is None:
            continue
        p1, p2 = a["full"][B], b["full"][B]
        p = (p1 + p2) / 2
        se = math.sqrt(max(p * (1 - p), 1e-4) * 2 / n)
        zs.append(abs(p1 - p2) / se)
        zs.append(abs(a["wanted"][B] - b["wanted"][B]) / (1.6 * math.sqrt(2 / n)))
    zs.append(abs(a["skills"] - b["skills"]) / (1.6 * math.sqrt(2 / n)))
    return max(zs)
F.simulate_plan_nb(H.get_horse(d, "Mythical Diné"), 1.2, "at30", runs=10)       # compile once
print(f"{'case':28} exact py==orig | z orig/nb (n=20000) | 99th pct of coupons needed orig/py/nb")
for lab, hn, tb, g, b, st, L, cap, kw in CASES:
    h = H.get_horse(d, hn); M = h.M(tb, g, b)
    args = (h, M, st, L, cap, 40)
    o = H.simulate_plan(*args, runs=40000, seed=3, **kw)
    p = o
    nbr = F.simulate_plan_nb(*args, runs=40000, seed=3, **kw)
    exact = "skip"
    q = lambda r: H.percentile(r["needed"], .99)
    print(f"{lab:28} {str(exact):14} | {cmp(o, nbr, 40000):5.2f} | {q(o)}/{q(p)}/{q(nbr)}")
# second numba seed, to see the spread of z between two numba runs too
print("numba seed 3 vs seed 4 (should look like noise):")
for lab, hn, tb, g, b, st, L, cap, kw in CASES[:6]:
    h = H.get_horse(d, hn); M = h.M(tb, g, b)
    a = F.simulate_plan_nb(h, M, st, L, cap, 40, runs=40000, seed=3, **kw)
    c = F.simulate_plan_nb(h, M, st, L, cap, 40, runs=40000, seed=4, **kw)
    print(f"  {lab:28} z {cmp(a, c, 40000):5.2f}")
