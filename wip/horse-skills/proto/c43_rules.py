"""C43 part 2: per-budget fit, a compact wording, and the current (travel) rule, for one target set.

From c43_<set>/ (stage-1 values, 1000 horses, and the reference best per case and budget). Loss = reference - plan,
points of the full-set chance; all cases count (no held-out horse this time).
  fit:      per budget, the plan with the smallest worst-case loss over the cases (then average loss); its
            cross-validated worst loss (2 halves x 5 random splits) is reported too.
  wording:  three bands (any can be empty): 1 coupon at30; 2..N1 'from level max(lo, round(c0 - a x N)), V2, keep k';
            N1+1..N2 'from level L, V0 until T learned skills, then V2, spend at most min(S, N - k)'; above N2 the same
            with its own L2, T2, S2, k2. Searched on the stage-1 values (a cap not on the grid is replaced by the largest
            grid cap below it for the search), minimizing the largest extra worst-case loss over the fit.
  current:  bdo.horses.rule_plan (the compact travel rule of 2026-11-21).
Rechecked: the fit's, the wording's (exact caps) and the current rule's plans, 4000 fresh horses per case (seed 3003).
Output: c43_<set>_rules.txt / .json. Usage: python3 -I c43_rules.py courser|travel10
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE))), HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
import c37r                                                              # noqa: E402
import c43                                                               # noqa: E402

NAME = sys.argv[1]
D = os.path.join(HERE, f"c43_{NAME}")
idx = json.load(open(os.path.join(D, "index.json")))
CASES, PLANS, C, WANTED = idx["cases"], [tuple(p) for p in idx["plans"]], idx["C"], idx["wanted"]
PIDX = {p: j for j, p in enumerate(PLANS)}
V = np.stack([np.load(os.path.join(D, f"{i}.npz"))["vals"] for i in range(len(CASES))])
REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(CASES))])
L = 100 * (REF[:, None, :] - V)
with np.errstate(all="ignore"):
    WL, AL = np.nanmax(L, 0), np.nanmean(L, 0)
CAPS = sorted({p[2] for p in PLANS if p[0]})
CODE = {v: k for k, v in c37r.NAME.items()}


def grid_cap(c):
    return max([x for x in CAPS if x <= c] or [None]) if c >= 1 else None


def v2(N, c0, a, lo, k):
    cap = N - k
    if cap < 1:
        return None
    return (6, int(min(29, max(lo, int(np.floor(c0 - a * N + 0.5))))), cap, 0, 0)


def sw(N, Lv, T, S, k):
    cap = min(S, N - k)
    return (12, Lv, cap, 0, T) if cap >= 1 else None


def look(p):
    """Grid index for the search (cap rounded down to the grid)."""
    if p is None:
        return None
    g = grid_cap(p[2])
    return PIDX.get((p[0], p[1], g, p[3], p[4])) if g else None


def fit_index(cases, B):
    with np.errstate(all="ignore"):
        Lc = L[cases][:, :, B]
        ok = ~np.isnan(Lc).any(0)
        w = np.where(ok, Lc.max(0), np.inf)
        a = np.where(ok, Lc.mean(0), np.inf)
    return int(np.lexsort((a, np.round(w, 2)))[0])


ALL = np.arange(len(CASES))
FIT = {B: fit_index(ALL, B) for B in range(1, C + 1)}


G_V2 = list(itertools.product([29, 30, 31, 32], [1.0, 1.25, 1.5, 1.75, 2.0], [2, 3, 4, 6, 8, 10, 12], [0, 1, 2]))
G_SW = list(itertools.product([2, 4, 6, 8, 10, 11, 12, 14], range(9, 18), [12, 15, 18, 20, 22, 24, 26, 30, 40], [0, 1, 2, 4]))


def extra(fn, grid):
    """Per parameter set and budget: extra worst-case and average loss over the fit (inf where not available)."""
    EW = np.full((len(grid), C + 1), np.inf)
    EA = np.full((len(grid), C + 1), np.inf)
    for g, prm in enumerate(grid):
        for N in range(1, C + 1):
            j = look(fn(N, *prm))
            if j is not None and not np.isnan(WL[j, N]):
                EW[g, N] = WL[j, N] - WL[FIT[N], N]
                EA[g, N] = AL[j, N] - AL[FIT[N], N]
    return EW, EA


EW1, EA1 = extra(v2, G_V2)
EW2, EA2 = extra(sw, G_SW)


def bestc(kind, lo, hi):
    """(score, params) of the best parameter set for budgets lo..hi: smallest largest extra worst loss (rounded to
    0.01), then smallest average extra average loss."""
    EW, EA, grid = (EW1, EA1, G_V2) if kind == "v2" else (EW2, EA2, G_SW)
    w = np.round(EW[:, lo:hi + 1].max(1), 2)
    a = EA[:, lo:hi + 1].mean(1)
    g = int(np.lexsort((a, w))[0])
    if not np.isfinite(w[g]):
        return None
    return ((float(w[g]), float(a[g])), grid[g])


results = []
for N1 in range(1, C + 1):
    b1 = bestc("v2", 2, N1) if N1 >= 2 else ((0.0, 0.0), None)
    for N2 in range(N1, C + 1):
        b2 = bestc("sw", N1 + 1, N2) if N2 > N1 else ((0.0, 0.0), None)
        b3 = bestc("sw", N2 + 1, C) if N2 < C else ((0.0, 0.0), None)
        if b1 and b2 and b3:
            results.append((max(b1[0][0], b2[0][0], b3[0][0]), b1[0][1] + b2[0][1] + b3[0][1],
                            (N1 > 1) + (N2 > N1) + (N2 < C), N1, N2, b1, b2, b3))
results.sort(key=lambda r: (r[0], r[2], r[1]))
top = results[0]
_, _, _, N1, N2, (s1, p1), (s2, p2), (s3, p3) = top


def wording(N):
    if N == 1:
        return (0, 1, 0, 0, 0)
    if N <= N1:
        return v2(N, *p1)
    if N <= N2:
        return sw(N, *p2)
    return sw(N, *p3)


WORD = {N: wording(N) for N in range(1, C + 1)}
CUR = {N: (CODE[H.rule_plan(N)[0]],) + tuple(H.rule_plan(N)[1:3]) + (0, H.rule_plan(N)[3]) for N in range(1, C + 1)}
FITP = {N: PLANS[j] for N, j in FIT.items()}

# cross-validated worst loss of the per-budget fit (2 halves x 5 splits)
rng = np.random.default_rng(7)
cvw = {N: [] for N in range(1, C + 1)}
for _ in range(5):
    perm = rng.permutation(len(CASES))
    for a, b in ((perm[: len(perm) // 2], perm[len(perm) // 2:]), (perm[len(perm) // 2:], perm[: len(perm) // 2])):
        for N in range(1, C + 1):
            cvw[N].append(float(np.nanmax(L[b, fit_index(a, N), N])))

fresh = {}
d = H.load_data()
for i, c in enumerate(CASES):
    ev = c43.evaluator(c, WANTED, d)
    keys = sorted({c37r.tool_plan(p, c["level"]) for r in (WORD, CUR, FITP) for p in r.values()})
    r = c37r.evaluate(ev, keys, 4000, 3003)
    for k in keys:
        fresh[(i, k)] = r[k]["full"]
    print(f"recheck {i + 1}/{len(CASES)}", flush=True)


def recheck(p, N):
    x = np.array([100 * (REF[i, N] - fresh[(i, c37r.tool_plan(p, c["level"]))][N]) for i, c in enumerate(CASES)])
    return float(x.max()), float(x.mean()), CASES[int(np.argmax(x))]["label"]


def name(p, N):
    st, s, cap, _, T = p
    return H.plan_name((c37r.NAME[st], s if st else 1, cap if st else 0, T), N)


lines = [f"# C43 {NAME}: {len(CASES)} cases, target {WANTED}",
         f"# wording bands: 1 | 2-{N1} V2 | {N1 + 1}-{N2} switch | {N2 + 1}-{C} switch  (empty bands allowed)",
         f"#  V2 band (c0, a, lo, k) = {p1}  (stage-1 extra worst over the fit {s1})",
         f"#  middle band (L, T, S, k) = {p2}  ({s2})", f"#  high band (L2, T2, S2, k2) = {p3}  ({s3})",
         "# next best: " + ", ".join(f"(worst {r[0]}, bands {r[2]}, N1 {r[3]}, N2 {r[4]})" for r in results[1:6]), "",
         "# rechecked with 4000 fresh horses per case (seed 3003): worst / average loss vs each case's reference best",
         "N\tfit plan\tfit worst/avg (CV worst)\twording plan\twording worst/avg\tcurrent rule worst/avg\twording worst case"]
out = {"bands": {"N1": N1, "N2": N2, "v2": p1, "mid": p2, "high": p3}, "per_budget": {}}
for N in range(1, C + 1):
    f, w, cu = recheck(FITP[N], N), recheck(WORD[N], N), recheck(CUR[N], N)
    lines.append(f"{N}\t{name(FITP[N], N)}\t{f[0]:.1f}/{f[1]:.1f} ({max(cvw[N]):.1f})\t{name(WORD[N], N)}\t"
                 f"{w[0]:.1f}/{w[1]:.1f}\t{cu[0]:.1f}/{cu[1]:.1f}\t{w[2]}")
    out["per_budget"][N] = {"fit": list(FITP[N]), "fit_recheck": f[:2], "fit_cv_worst": max(cvw[N]),
                            "wording": list(WORD[N]), "wording_recheck": w[:2], "current": list(CUR[N]),
                            "current_recheck": cu[:2]}
open(os.path.join(HERE, f"c43_{NAME}_rules.txt"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, f"c43_{NAME}_rules.json"), "w"))
print("\n".join(lines))
