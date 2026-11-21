"""C43 full version, part 2: per-budget fit, a compact wording (improved search), and the current rule, for one
target set, from c43f_<set>/ (full grid). Loss = reference best - plan, points of the full-set chance; all cases.
  fit:      per budget, the plan with the smallest worst-case loss over the cases (then average); cross-validated worst
            (2 halves x 5 random splits).
  wording:  up to four bands (each may be empty), every plan exactly on the grid:
            1 coupon: at30;
            small 2..Ns: from level max(lo, round(c0 - a x N)) (halves up), V2 or 'V0 until T, then V2', keep k;
            V2    Ns+1..N1: from level max(lo, round(c0 - a x N)), V2, keep k;
            mid   N1+1..N2: from level L, V0 until T learned skills, then V2, spending at most min(S, N - k);
            high  N2+1..40: the same with its own L, T, S, k.
            Score: the largest extra worst-case loss over the fit across budgets, rounded to 0.5 points (so a few
            budgets where nothing compact is close don't decide everything); then the fewest bands among wordings
            whose mean extra worst-case loss is within 0.05 points of the best; then that mean.
  current:  bdo.horses.rule_plan.
Rechecked: fit, wording and current plans with 4000 fresh horses per case (seed 3003).
Output: c43f_<set>_rules.txt / .json. Usage: python3 -I c43f_rules.py courser|travel10
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
D = os.path.join(HERE, f"c43f_{NAME}")
idx = json.load(open(os.path.join(D, "index.json")))
CASES, PLANS, C, WANTED = idx["cases"], [tuple(p) for p in idx["plans"]], idx["C"], idx["wanted"]
PIDX = {p: j for j, p in enumerate(PLANS)}
V = np.stack([np.load(os.path.join(D, f"{i}.npz"))["vals"] for i in range(len(CASES))])
REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(CASES))])
L = 100 * (REF[:, None, :] - V)
with np.errstate(all="ignore"):
    WL, AL = np.nanmax(L, 0), np.nanmean(L, 0)
CODE = {v: k for k, v in c37r.NAME.items()}


def start(N, c0, a, lo):
    return int(min(29, max(lo, int(np.floor(c0 - a * N + 0.5)))))


def small(N, c0, a, lo, T, k):
    return (6, start(N, c0, a, lo), N - k, 0, 0) if T == 0 else (12, start(N, c0, a, lo), N - k, 0, T)


def v2(N, c0, a, lo, k):
    return (6, start(N, c0, a, lo), N - k, 0, 0)


def sw(N, Lv, T, S, k):
    return (12, Lv, min(S, N - k), 0, T)


def fit_index(cases, B):
    with np.errstate(all="ignore"):
        Lc = L[cases][:, :, B]
        ok = ~np.isnan(Lc).any(0)
        w = np.where(ok, Lc.max(0), np.inf)
        a = np.where(ok, Lc.mean(0), np.inf)
    return int(np.lexsort((a, np.round(w, 2)))[0])


ALL = np.arange(len(CASES))
FIT = {B: fit_index(ALL, B) for B in range(1, C + 1)}
STARTS = dict(c0=[29, 30, 31, 32], a=[1.0, 1.25, 1.5, 1.75, 2.0, 2.5], lo=[2, 4, 6, 8, 10, 12])
G = {"small": list(itertools.product(STARTS["c0"], STARTS["a"], STARTS["lo"], [0] + list(range(9, 18)), [0, 1, 2])),
     "v2": list(itertools.product(STARTS["c0"], STARTS["a"], STARTS["lo"], [0, 1, 2, 3])),
     "sw": list(itertools.product([2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14], range(9, 18),
                                  [12, 15, 18, 20, 22, 24, 26, 30, 35, 40], range(0, 7)))}
FN = {"small": small, "v2": v2, "sw": sw}


def extra(kind):
    EW = np.full((len(G[kind]), C + 1), np.inf)
    for g, prm in enumerate(G[kind]):
        for N in range(2, C + 1):
            p = FN[kind](N, *prm)
            j = PIDX.get(p) if p[2] >= 1 else None
            if j is not None and not np.isnan(WL[j, N]):
                EW[g, N] = WL[j, N] - WL[FIT[N], N]
    return EW


EW = {k: extra(k) for k in G}
cache = {}


def band(kind, lo, hi):
    """(rounded max extra, sum of extras, params) of the best parameter set over budgets lo..hi (None if empty)."""
    if hi < lo:
        return (0.0, 0.0, None)
    key = (kind, lo, hi)
    if key not in cache:
        E = EW[kind][:, lo:hi + 1]
        m = np.round(E.max(1) * 2) / 2
        s = E.sum(1)
        g = int(np.lexsort((s, m))[0])
        cache[key] = (float(m[g]), float(s[g]), G[kind][g]) if np.isfinite(m[g]) else None
    return cache[key]


results = []
for Ns in range(1, C + 1):
    bs = band("small", 2, Ns)
    if bs is None:
        continue
    for N1 in range(Ns, C + 1):
        b1 = band("v2", Ns + 1, N1)
        if b1 is None:
            continue
        for N2 in range(N1, C + 1):
            b2, b3 = band("sw", N1 + 1, N2), band("sw", N2 + 1, C)
            if b2 is None or b3 is None:
                continue
            nb = (Ns > 1) + (N1 > Ns) + (N2 > N1) + (N2 < C)
            results.append((max(bs[0], b1[0], b2[0], b3[0]), (bs[1] + b1[1] + b2[1] + b3[1]) / (C - 1), nb,
                            Ns, N1, N2, bs, b1, b2, b3))
# smallest max; among those, fewest bands whose mean is within 0.05 points of the best mean; then the best mean
mx = min(r[0] for r in results)
cand = [r for r in results if r[0] == mx]
best_mean = min(r[1] for r in cand)
cand = [r for r in cand if r[1] <= best_mean + 0.05]
cand.sort(key=lambda r: (r[2], r[1]))
results = cand + sorted([r for r in results if r not in cand], key=lambda r: (r[0], r[1], r[2]))
_, _, _, Ns, N1, N2, bs, b1, b2, b3 = results[0]


def wording(N):
    if N == 1:
        return (0, 1, 0, 0, 0)
    if N <= Ns:
        return small(N, *bs[2])
    if N <= N1:
        return v2(N, *b1[2])
    if N <= N2:
        return sw(N, *b2[2])
    return sw(N, *b3[2])


WORD = {N: wording(N) for N in range(1, C + 1)}
CUR = {N: (CODE[H.rule_plan(N)[0]],) + tuple(H.rule_plan(N)[1:3]) + (0, H.rule_plan(N)[3]) for N in range(1, C + 1)}
CUR = {N: (p if p[0] else (0, 1, 0, 0, 0)) for N, p in CUR.items()}
FITP = {N: PLANS[j] for N, j in FIT.items()}
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


lines = [f"# C43 full {NAME}: {len(CASES)} cases, target {WANTED}",
         f"# wording bands: 1 | small 2-{Ns} | V2 {Ns + 1}-{N1} | mid {N1 + 1}-{N2} | high {N2 + 1}-{C} (empty if lo > hi)",
         f"#  small (c0, a, lo, T (0 = V2), k) = {bs[2]}  (stage-1 max extra worst {bs[0]})",
         f"#  V2 (c0, a, lo, k) = {b1[2]}  ({b1[0]})", f"#  mid (L, T, S, k) = {b2[2]}  ({b2[0]})",
         f"#  high (L, T, S, k) = {b3[2]}  ({b3[0]})",
         "# next best: " + ", ".join(f"(max {r[0]}, mean {r[1]:.2f}, bands {r[2]}: {r[3]}/{r[4]}/{r[5]})" for r in results[1:6]),
         "", "# rechecked with 4000 fresh horses per case (seed 3003): worst / average loss vs each case's reference best",
         "N\tfit plan\tfit worst/avg (CV worst)\twording plan\twording worst/avg\tcurrent rule worst/avg\twording worst case"]
out = {"bands": {"Ns": Ns, "N1": N1, "N2": N2, "small": bs[2], "v2": b1[2], "mid": b2[2], "high": b3[2]},
       "per_budget": {}}
for N in range(1, C + 1):
    f, w, cu = recheck(FITP[N], N), recheck(WORD[N], N), recheck(CUR[N], N)
    lines.append(f"{N}\t{name(FITP[N], N)}\t{f[0]:.1f}/{f[1]:.1f} ({max(cvw[N]):.1f})\t{name(WORD[N], N)}\t"
                 f"{w[0]:.1f}/{w[1]:.1f}\t{cu[0]:.1f}/{cu[1]:.1f}\t{w[2]}")
    out["per_budget"][N] = {"fit": list(FITP[N]), "fit_recheck": f[:2], "fit_cv_worst": max(cvw[N]),
                            "wording": list(WORD[N]), "wording_recheck": w[:2], "current": list(CUR[N]),
                            "current_recheck": cu[:2]}
open(os.path.join(HERE, f"c43f_{NAME}_rules.txt"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, f"c43f_{NAME}_rules.json"), "w"))
print("\n".join(lines))
