"""C37r S1: compact rule wordings, scored on the stored C37r values (c37r_cases), then rechecked with fresh horses.

Wording (three bands, N = coupons):
  N = 1: no swaps while leveling, the coupon at level 30.
  2..N1: from level max(lo, round(c0 - a x N)), do V2 until level 30, keep k (k = 1 up to kb coupons, else k2).
  N1+1..N2: from level L, do V0 until T learned skills, then V2 until level 30, keep K.
  above N2: from level L2, do V0 until T2 learned skills, then V2 until level 30, spending at most min(S, N) while
            leveling (S on the grid's caps).
Parameters searched on the grid's plans; per band, the choice minimizes the band's largest extra worst-case loss
over the per-budget fit (worst over the 72 reliable cases, stage-1 values vs the reference), then the average extra
average loss; band edges N1, N2 chosen the same way over 2..40. (v1 minimized the raw worst loss: the 2-4 coupon
budgets, bad for every plan, decided everything; its output is kept as c37r_wording_v1.txt.) Then the wording's plans and the per-budget fit (c37r_rules.json
'any plan') are rechecked together with 4000 fresh horses per case (seed 3003, same horses for both).
Output: c37r_wording.txt, c37r_wording.json. Usage: python3 -I c37r_wording.py
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE))), HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402
import c37                                                               # noqa: E402
import c37r                                                              # noqa: E402

D = os.path.join(HERE, "c37r_cases")
idx = json.load(open(os.path.join(D, "index.json")))
CASES, PLANS, C = idx["cases"], [tuple(p) for p in idx["plans"]], idx["C"]
PIDX = {p: j for j, p in enumerate(PLANS)}
V = np.stack([np.load(os.path.join(D, f"{i}.npz"))["vals"] for i in range(len(CASES))])
REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(CASES))])
REL = np.array([c["reliable"] for c in CASES])
L = 100 * (REF[REL][:, None, :] - V[REL])                                # reliable case x plan x budget
WL, AL = np.nanmax(L, 0), np.nanmean(L, 0)                               # plan x budget
CAPS = c37r.CAPS


def v2(N, c0, a, lo, kb, k2):
    k = 1 if N <= kb else k2
    return PIDX.get((6, int(min(29, max(lo, round(c0 - a * N)))), N - k, 0, 0))


def mid(N, Lv, T, K):
    return PIDX.get((12, Lv, N - K, 0, T)) if N - K >= 1 else None


def high(N, Lv, T, S):
    cap = max(c for c in CAPS if c <= min(S, N))
    return PIDX.get((12, Lv, cap, 0, T))


def score(fn, params, budgets):
    """(largest worst loss over budgets, average of the average losses), or None if a plan isn't in the grid."""
    w, a = [], []
    for N in budgets:
        j = fn(N, *params)
        if j is None or np.isnan(WL[j, N]):
            return None
        w.append(WL[j, N] - WL[FIT[N], N]); a.append(AL[j, N] - AL[FIT[N], N])
    return (round(float(max(w)), 2), float(np.mean(a)))


fit = json.load(open(os.path.join(HERE, "c37r_rules.json")))
CODE = {v: k for k, v in c37r.NAME.items()}
FIT = {}
for N in range(1, C + 1):
    st, s, cap, T = fit[str(N)]["any plan"]["plan"]
    FIT[N] = PIDX[(CODE[st], s if st != "at30" else 1, cap if st != "at30" else 0, 0, T)]
G_V2 = list(itertools.product([29, 30, 31], [1.25, 1.5, 1.75, 2.0], [2, 3, 4, 6, 8, 10], [8, 10, 12, 14, 40], [1, 2, 3]))
G_MID = list(itertools.product([8, 9, 10, 11, 12], range(9, 15), [1, 2, 3, 4, 5, 6]))
G_HIGH = list(itertools.product([2, 4, 6, 8, 10], range(11, 17), [16, 18, 20, 22, 24, 26, 30, 35, 40]))


def best(fn, grid, budgets):
    s = [(score(fn, p, budgets), p) for p in grid]
    s = [x for x in s if x[0] is not None]
    return min(s) if s else None


results = []
for N1 in range(15, 23):
    for N2 in range(N1 + 2, 31):
        b1 = best(v2, G_V2, range(2, N1 + 1))
        b2 = best(mid, G_MID, range(N1 + 1, N2 + 1))
        b3 = best(high, G_HIGH, range(N2 + 1, C + 1))
        if b1 and b2 and b3:
            results.append((max(b1[0][0], b2[0][0], b3[0][0]), b1[0][1] + b2[0][1] + b3[0][1], N1, N2, b1, b2, b3))
results.sort()
top = results[0]
_, _, N1, N2, (s1, p1), (s2, p2), (s3, p3) = top


def wording(N):
    if N == 1:
        return PIDX[(0, 1, 0, 0, 0)]
    if N <= N1:
        return v2(N, *p1)
    if N <= N2:
        return mid(N, *p2)
    return high(N, *p3)


fitted = FIT
words = {N: wording(N) for N in range(1, C + 1)}

d = H.load_data()
fresh = {}
for i, c in enumerate(CASES):
    h = H.get_horse(d, c["horse"])
    g, b = c37.BOOSTS[c["boost"]]
    ev = F.Evaluator(h, h.M(H.training_bonus(c["training"]), g, b), max_budget=C, learned=c["learned"],
                     start_level=c["level"])
    keys = sorted({c37r.tool_plan(PLANS[j], c["level"]) for j in list(words.values()) + list(fitted.values())})
    r = c37r.evaluate(ev, keys, 4000, 3003)
    for k in keys:
        fresh[(i, k)] = r[k]["full"]
    print(f"recheck {i + 1}/{len(CASES)}", flush=True)


def recheck(j, N):
    Lc = np.array([100 * (REF[i, N] - fresh[(i, c37r.tool_plan(PLANS[j], c["level"]))][N]) for i, c in enumerate(CASES)])
    lr = Lc[REL]
    return float(lr.max()), float(lr.mean()), float(Lc[~REL].max()), CASES[int(np.where(REL)[0][np.argmax(lr)])]["label"]


lines = [f"# C37r S1: compact wording. Bands: 1 | 2-{N1} V2 | {N1 + 1}-{N2} V0 then V2 | {N2 + 1}-40 V0 then V2.",
         f"# V2 band: from level max({p1[2]}, round({p1[0]} - {p1[1]} x N)), keep 1 up to {p1[3]} coupons, else {p1[4]}."
         f"  (stage-1 band score, extra over the fit: worst {s1[0]}, avg {s1[1]:.2f})",
         f"# middle band: from level {p2[0]}, V0 until {p2[1]} learned skills, then V2, keep {p2[2]}."
         f"  (worst {s2[0]}, avg {s2[1]:.2f})",
         f"# high band: from level {p3[0]}, V0 until {p3[1]} learned skills, then V2, spend at most {p3[2]} while "
         f"leveling.  (worst {s3[0]}, avg {s3[1]:.2f})",
         "# next best band edges (overall worst, N1, N2): " + ", ".join(f"({r[0]}, {r[2]}, {r[3]})" for r in results[1:6]),
         "", "# Rechecked with 4000 fresh horses per case (seed 3003), worst / average loss over the 72 reliable cases"
         " (points), Arduanatt worst; wording vs the per-budget fit",
         "N\twording plan\twording worst\tavg\tArd\tfit plan\tfit worst\tavg\tArd\twording worst case"]
out = {"bands": {"N1": N1, "N2": N2, "v2": p1, "mid": p2, "high": p3}, "per_budget": {}}
for N in range(1, C + 1):
    a, b = recheck(words[N], N), recheck(fitted[N], N)
    lines.append(f"{N}\t{H.plan_name(c37r.tool_plan(PLANS[words[N]], 1), N)}\t{a[0]:.1f}\t{a[1]:.1f}\t{a[2]:.1f}\t"
                 f"{H.plan_name(c37r.tool_plan(PLANS[fitted[N]], 1), N)}\t{b[0]:.1f}\t{b[1]:.1f}\t{b[2]:.1f}\t{a[3]}")
    out["per_budget"][N] = {"wording": list(c37r.tool_plan(PLANS[words[N]], 1)), "wording_recheck": a[:3],
                            "fit": list(c37r.tool_plan(PLANS[fitted[N]], 1)), "fit_recheck": b[:3]}
open(os.path.join(HERE, "c37r_wording.txt"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, "c37r_wording.json"), "w"))
print("\n".join(lines))
