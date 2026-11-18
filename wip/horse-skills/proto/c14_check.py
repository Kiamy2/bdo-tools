"""C14 B1: does the agreed rule wording lose against the fitted per-budget plans? Paired, from the stored C37/C37b
stage-1 values (same horses for every plan of a case). Loss = best plan of the case - this plan, in points;
worst over the reliable cases (Arduanatt left out, as in C37). Wording ranges: every plan they allow is checked."""
import json
import numpy as np

def load(d):
    ix = json.load(open(f"{d}/index.json"))
    keep = [i for i, c in enumerate(ix["cases"]) if c["reliable"]]
    V = np.stack([np.load(f"{d}/{i}.npz")["vals"] for i in keep])          # case x plan x budget
    P = {tuple(p): j for j, p in enumerate(ix["plans"])}
    return V, P

def worst(V, P, plans, B):
    js = [P[p] for p in plans if p in P]
    if not js:
        return None, 0
    best = np.nanmax(V[:, :, B], axis=1)
    loss = 100 * (best[:, None] - V[:, js, B])                            # case x plan
    return np.nanmax(loss, axis=0), len(js)                               # worst case, per allowed plan

b = json.load(open("c37b_rules.json")); a = json.load(open("c37_rules.json"))
fitted = {int(k): tuple(v["any plan"]["plan"]) for src in (a, b) for k, v in src.items()}
rows = []
for d, budgets in (("c37b_cases", range(16, 25)), ("c37_cases", (25, 26, 30, 35, 40))):
    V, P = load(d)
    for B in budgets:
        fb = max(k for k in fitted if k <= B)
        fp = fitted[fb]
        wf, _ = worst(V, P, [fp], B)
        if B <= 17:
            s = int(round(29 - 1.5 * B))
            wording = [(6, s, c, 0, 0) for c in (B, B - 1, B - 2)]
            text = f"V2 from {s}, keep 0-2"
        elif B <= 24:
            wording = [(12, 10, B - k, 0, T) for k in (3, 4, 5) for T in (11, 12)]
            text = "from 10, V0 until 11-12, keep 3-5"
        else:
            wording = [(12, s, B - k, 0, T) for s in (2, 3, 4) for k in (0, 1, 2) for T in (13, 14, 15)]
            text = "from 2-4, V0 until 13-15, keep 0-2"
        ww, n = worst(V, P, wording, B)
        rows.append((B, fp, None if wf is None else float(wf[0]), text, n,
                     None if ww is None else (float(ww.min()), float(ww.max()))))
print("budget | fitted plan (from the fit at <= budget) | its worst loss | wording | plans in grid | worst loss over them: best-worst")
for B, fp, wf, text, n, ww in rows:
    f = "-" if wf is None else f"{wf:.1f}"
    w = "not in grid" if ww is None else f"{ww[0]:.1f} - {ww[1]:.1f}"
    print(f"{B} | {fp} | {f} | {text} | {n} | {w}")
