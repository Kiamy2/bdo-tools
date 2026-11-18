"""C37b band refinement (16-24 coupons), part 2: one plan per budget for everyone, cross-validated.

Loss of a plan in a case = the case's best chance (reference) minus the plan's chance, in percentage points of the
full-set chance. For each budget and rule family, the plan with the smallest worst-case loss over the fitting cases
is chosen. 2-fold cross-validation over the reliable cases (random halves, 5 different splits): choose on one half,
measure on the other. Then the rules chosen on all reliable cases are rechecked with fresh horses in every case.
Output: c37_rules.txt, c37_rules.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402

D = os.path.join(HERE, "c37b_cases")
idx = json.load(open(os.path.join(D, "index.json")))
CASES, PLANS, C = idx["cases"], [tuple(p) for p in idx["plans"]], idx["C"]
V = np.stack([np.load(os.path.join(D, f"{i}.npz"))["vals"] for i in range(len(CASES))])     # case x plan x budget
REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(CASES))])    # case x budget
LOSS = 100 * (REF[:, None, :] - V)
REL = np.array([c["reliable"] for c in CASES])
CAPS = sorted({p[2] for p in PLANS if p[0]})


def c29_plan(B):
    s = int(max(2, round(29 - 1.5 * B)))
    cap = max([c for c in CAPS if c <= B] or [min(CAPS)])
    return PLANS.index((6, min(s, 29), cap, 0, 0))


FAMILIES = {
    "any plan": [j for j, p in enumerate(PLANS)],
    "V0": [j for j, p in enumerate(PLANS) if p[0] == 1],
    "V2": [j for j, p in enumerate(PLANS) if p[0] == 6],
    **{f"V0 until {T} held": [j for j, p in enumerate(PLANS) if p[0] == 12 and p[4] == T] for T in range(9, 17)},
    "V0 until T held (any T)": [j for j, p in enumerate(PLANS) if p[0] == 12],
}


def choose(cases, fam, B):
    js = [j for j in FAMILIES[fam] if not np.isnan(V[cases, j, B]).any()]
    if not js:
        return None
    L = LOSS[np.ix_(cases, js, [B])][:, :, 0]
    worst, avg = L.max(0), L.mean(0)
    k = min(range(len(js)), key=lambda i: (round(float(worst[i]), 2), float(avg[i])))
    return js[k]


def describe(j, B):
    st, s, cap, xa, T = PLANS[j]
    name = {0: "All at 30", 1: "V0", 6: "V2", 12: f"V0 until {T} held, then V2"}[st]
    return name if st == 0 else f"{name}, start {s}, keep {max(0, B - cap)}"


rel = np.where(REL)[0]
rng = np.random.default_rng(7)
BUDGETS = list(range(16, 25))
cv = {fam: {B: [] for B in BUDGETS} for fam in list(FAMILIES) + ["C29 rule (V2 from 29 - 1.5 x coupons)"]}
for split in range(5):
    perm = rng.permutation(rel)
    halves = (perm[: len(perm) // 2], perm[len(perm) // 2:])
    for a, b in ((0, 1), (1, 0)):
        fit, test = halves[a], halves[b]
        for B in BUDGETS:
            for fam in FAMILIES:
                j = choose(fit, fam, B)
                if j is not None:
                    cv[fam][B].append(LOSS[test, j, B])
            cv["C29 rule (V2 from 29 - 1.5 x coupons)"][B].append(LOSS[test, c29_plan(B), B])
lines = ["# C37: loss (percentage points of the full-set chance) of one plan per budget for everyone.",
         "# Cross-validated: chosen on half of the reliable cases, measured on the other half (5 random splits x 2).",
         "# Cells: worst loss / average loss on the held-out cases.", ""]
lines.append("rule family\t" + "\t".join(f"{B} coupons" for B in BUDGETS))
for fam in cv:
    cells = []
    for B in BUDGETS:
        if not cv[fam][B]:
            cells.append("-")
            continue
        x = np.concatenate(cv[fam][B])
        cells.append(f"{x.max():.1f} / {x.mean():.1f}")
    lines.append(f"{fam}\t" + "\t".join(cells))

# final rules: chosen on all reliable cases, rechecked with fresh horses in every case
sys.path.insert(0, HERE)
from bdo import horses as H                                              # noqa: E402
import c36_fast as X                                                     # noqa: E402
import c37b as c37                                                               # noqa: E402
final = {}
for fam in ("any plan", "V2", "V0 until T held (any T)", "V0 until 11 held", "V0 until 12 held", "V0 until 13 held"):
    final[fam] = {B: choose(rel, fam, B) for B in range(1, C + 1)}
final["C29 rule (V2 from 29 - 1.5 x coupons)"] = {B: c29_plan(B) for B in range(1, C + 1)}
d = H.load_data()
fresh = {}
tables = {}
for i, c in enumerate(CASES):
    h = H.get_horse(d, c["horse"])
    if c["horse"] not in tables:
        tables.clear()
    g, b = c37.BOOSTS[c["boost"]]
    ev = X.Evaluator(h, h.M(H.training_bonus(c["training"]), g, b), C=C, table=tables.get(c["horse"]),
                     learned=c["learned"], start_level=c["level"])
    tables[c["horse"]] = ev.table
    for fam, rule in final.items():
        for B, j in rule.items():
            if j is None:
                continue
            st, s, cap, xa, xb = PLANS[j]
            key = (st, max(s, c["level"] + 1) if st else s, cap, xa, xb)
            if (i, key) not in fresh:
                fresh[(i, key)] = ev.plan(*key, runs=4000, seed=2002)
    print(f"recheck {i + 1}/{len(CASES)}", flush=True)
lines += ["", "# Rules chosen on all reliable cases, rechecked with 4000 fresh horses per case (worst / average loss;",
          "# 'Arduanatt' = worst loss on the Arduanatt cases, left out of the fitting: its no-skill weight is unchecked).",
          "budget\trule family\tplan\tworst\taverage\tArduanatt worst\tworst case"]
out = {}
for B in BUDGETS:
    for fam, rule in final.items():
        j = rule.get(B)
        if j is None:
            continue
        st, s, cap, xa, xb = PLANS[j]
        L = []
        for i, c in enumerate(CASES):
            key = (st, max(s, c["level"] + 1) if st else s, cap, xa, xb)
            L.append(100 * (REF[i, B] - fresh[(i, key)][B]))
        L = np.array(L)
        lr, la = L[REL], L[~REL]
        wc = CASES[int(np.where(REL)[0][np.argmax(lr)])]["label"]
        lines.append(f"{B}\t{fam}\t{describe(j, B)}\t{lr.max():.1f}\t{lr.mean():.1f}\t{la.max():.1f}\t{wc}")
        out.setdefault(str(B), {})[fam] = {"plan": list(map(int, PLANS[j])), "worst": float(lr.max()),
                                           "avg": float(lr.mean()), "arduanatt_worst": float(la.max())}
open(os.path.join(HERE, "c37b_rules.txt"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, "c37b_rules.json"), "w"))
print("\n".join(lines))
