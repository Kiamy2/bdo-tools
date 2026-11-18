"""C36 v2-vs-v0-hard: coupons needed for 90/95/99% of the full set, best plan of each family, hard and easy cases.

Per case and family: a coarse grid of plans (1000 horses each), then the neighbours of each family's best plans
(also 1000), then for every budget the family's top 3 rerun with 4000 fresh horses; the family's curve is the best
rerun value per budget. Output: c36_results.json and c36_summary.txt.
"""
import itertools
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
import c36_fast as X                                                     # noqa: E402

C = 50
CASES = [  # (label, horse, Training level, reliable)
    ("Diné Beginner 1", "Mythical Diné", "Beginner 1", True),
    ("Diné Skilled 1", "Mythical Diné", "Skilled 1", True),
    ("Diné Professional 10", "Mythical Diné", "Professional 10", True),
    ("Diné Artisan 7 (easy check)", "Mythical Diné", "Artisan 7", True),
    ("Doom Beginner 1", "Doom (T9)", "Beginner 1", True),
    ("Doom Skilled 1", "Doom (T9)", "Skilled 1", True),
    ("Doom Artisan 7 (easy check)", "Doom (T9)", "Artisan 7", True),
    ("T8 Beginner 1", "T8 example (bdolytics icon horse_71)", "Beginner 1", True),
    ("T8 Skilled 1", "T8 example (bdolytics icon horse_71)", "Skilled 1", True),
    ("T8 Professional 10", "T8 example (bdolytics icon horse_71)", "Professional 10", True),
    ("Arduanatt Skilled 1 (W unchecked)", "Mythical Arduanatt", "Skilled 1", False),
    ("Voltarion Skilled 1 (W unchecked)", "Voltarion", "Skilled 1", False),
]
STARTS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
CAPS = [2, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30, 35, 40, 45, 50]
CAPS_S = [6, 10, 15, 20, 30, 40, 50]
FAMILIES = {
    "All at 30": [(0, 1, 0, 0, 0)],
    "V0": [(1, s, c, 0, 0) for s in STARTS for c in CAPS],
    "V2": [(6, s, c, 0, 0) for s in STARTS for c in CAPS],
    "V0 then V2 at level L": [(10, s, c, L, 0) for s in (2, 6, 10, 14, 18, 22) for L in (8, 12, 16, 20, 24, 27)
                              for c in CAPS_S if L > s],
    "V2 then V0 at level L": [(11, s, c, L, 0) for s in (2, 6, 10, 14, 18, 22) for L in (8, 12, 16, 20, 24, 27)
                              for c in CAPS_S if L > s],
    "V0 until T skills, then V2": [(12, s, c, 0, T) for s in (2, 6, 10, 14, 18, 22) for T in range(11, 20)
                                   for c in CAPS_S],
    "V2, V0 from level L if under T skills": [(13, s, c, L, T) for s in (2, 6, 10, 14, 18, 22) for L in (12, 16, 20, 24)
                                              for T in (12, 14, 16, 18) for c in (10, 20, 30, 50) if L >= s],
}
STEP = {1: 1, 2: 1, 3: 1, 4: 1}                     # neighbour steps for (start, cap, xa, xb)


def neighbours(p):
    st, s, c, xa, xb = p
    out = set()
    for ds, dc, da, db in itertools.product((-1, 0, 1), (-1, 0, 1), (-1, 0, 1), (-1, 0, 1)):
        q = (st, s + ds, c + dc, xa + (da if st in (10, 11, 13) else 0), xb + (db if st in (12, 13) else 0))
        if 2 <= q[1] <= 29 and 1 <= q[2] <= C and (st not in (10, 11) or q[3] > q[1]) and (st != 13 or q[3] >= 2):
            out.add(q)
    return out


d = H.load_data()
tables = {}
results = {}
lines = []
for label, hn, tr, reliable in CASES:
    t0 = time.time()
    h = H.get_horse(d, hn)
    if hn not in tables:
        tables.clear()
    ev = X.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), C=C, table=tables.get(hn))
    tables[hn] = ev.table
    curves = {}
    for fam, plans in FAMILIES.items():
        s1 = {p: ev.plan(*p, runs=1000, seed=1) for p in plans}
        if fam != "All at 30":
            top = set()
            for B in range(1, C + 1):
                ok = [p for p in s1 if not np.isnan(s1[p][B])]
                top.update(sorted(ok, key=lambda p: -s1[p][B])[:1])
            for p in list(top):
                for q in neighbours(p):
                    if q not in s1:
                        s1[q] = ev.plan(*q, runs=1000, seed=1)
        keep = set()
        for B in range(C + 1):
            ok = [p for p in s1 if not np.isnan(s1[p][B])]
            keep.update(sorted(ok, key=lambda p: -s1[p][B])[:3])
        s2 = {p: ev.plan(*p, runs=4000, seed=1001) for p in keep}
        curve = [max((s2[p][B] for p in s2 if not np.isnan(s2[p][B])), default=float("nan")) for B in range(C + 1)]
        best = {B: max((p for p in s2 if not np.isnan(s2[p][B])), key=lambda p: s2[p][B]) for B in range(1, C + 1)
                if any(not np.isnan(s2[p][B]) for p in s2)}
        curves[fam] = {"curve": curve, "best": {B: list(map(int, p)) for B, p in best.items()}}
    need = {fam: {t: next((B for B, x in enumerate(v["curve"]) if x >= t), None) for t in (0.9, 0.95, 0.99)}
            for fam, v in curves.items()}
    results[label] = {"reliable": reliable, "curves": curves, "need": need}
    row = f"{label}\t" + "\t".join(f"{fam}: " + "/".join("-" if need[fam][t] is None else str(need[fam][t])
                                                       for t in (0.9, 0.95, 0.99)) for fam in curves)
    lines.append(row)
    print(f"{label}: {time.time() - t0:.0f}s, table {ev.table.rows} rows | " + row.split("\t", 1)[1], flush=True)
    json.dump(results, open(os.path.join(HERE, "c36_results.json"), "w"))
open(os.path.join(HERE, "c36_summary.txt"), "w").write(
    "# coupons needed for 90/95/99% of the full set (- = more than 50), best plan of each family\n" + "\n".join(lines) + "\n")
print("done", flush=True)
