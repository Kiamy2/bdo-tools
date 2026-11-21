"""C37r part 2 (with the points reset): one plan per budget for everyone, cross-validated; the current rule checked.

As c37_rules.py / c37b_rules.py, on c37r_cases (merged grid, budgets 0..40). Loss of a plan in a case = the case's
reference best chance - the plan's chance, in points of the full-set chance; families' plans chosen by smallest
worst-case loss over the fitting cases (reliable cases: Arduanatt left out, its no-skill weight unchecked), then
average loss. 2-fold cross-validation, 5 random splits. Then, chosen on all reliable cases and rechecked with 4000
fresh horses in every case (fast engine): the families' plans, the current rule (bdo.horses.rule_plan, fitted
without the reset) and the candidate wording 'V2 up to 17 coupons, else V0 until floor(N/2) + 1 learned skills (at most 15), then V2'
(best start level and cap for that T, chosen the same way).
Output: c37r_rules.txt, c37r_rules.json. Usage: python3 -I c37r_rules.py
"""
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
V = np.stack([np.load(os.path.join(D, f"{i}.npz"))["vals"] for i in range(len(CASES))])     # case x plan x budget
REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(CASES))])    # case x budget
LOSS = 100 * (REF[:, None, :] - V)
REL = np.array([c["reliable"] for c in CASES])
CODE = {v: k for k, v in c37r.NAME.items()}


def tool_to_grid(plan):
    st, s, cap, T = plan
    return PIDX[(CODE[st], s if st != "at30" else 1, cap if st != "at30" else 0, 0, T)]


FAMILIES = {
    "any plan": list(range(len(PLANS))),
    "V0": [j for j, p in enumerate(PLANS) if p[0] == 1],
    "V2": [j for j, p in enumerate(PLANS) if p[0] == 6],
    "V0 until T, then V2 (any T)": [j for j, p in enumerate(PLANS) if p[0] == 12],
    **{f"V0 until {T}, then V2": [j for j, p in enumerate(PLANS) if p[0] == 12 and p[4] == T] for T in c37r.TS},
}


def wording_fam(B):
    """Candidate wording: V2 up to 17 coupons, else V0 until floor(N/2) + 1 learned skills (at most 15)."""
    return "V2" if B <= 17 else f"V0 until {min(15, B // 2 + 1)}, then V2"


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
    return H.plan_name(c37r.tool_plan(PLANS[j], 1), B)


rel = np.where(REL)[0]
rng = np.random.default_rng(7)
BUDGETS = [5, 8, 10, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 30, 35, 40]
cv = {fam: {B: [] for B in BUDGETS} for fam in list(FAMILIES) + ["wording: V2 to 17, then T = floor(N/2) + 1 (<= 15)"]}
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
            j = choose(fit, wording_fam(B), B)
            cv["wording: V2 to 17, then T = floor(N/2) + 1 (<= 15)"][B].append(LOSS[test, j, B])
lines = ["# C37r (points reset): loss (points of the full-set chance) of one plan per budget for everyone.",
         "# Cross-validated: chosen on half of the reliable cases, measured on the other half (5 random splits x 2).",
         "# Cells: worst loss / average loss on the held-out cases.", ""]
lines.append("rule family\t" + "\t".join(f"{B}" for B in BUDGETS))
for fam in cv:
    cells = []
    for B in BUDGETS:
        x = np.concatenate(cv[fam][B]) if cv[fam][B] else None
        cells.append("-" if x is None else f"{x.max():.1f}/{x.mean():.1f}")
    lines.append(f"{fam}\t" + "\t".join(cells))

final = {fam: {B: choose(rel, fam, B) for B in range(1, C + 1)}
         for fam in ("any plan", "V2", "V0 until T, then V2 (any T)")}
final["wording: V2 to 17, then T = floor(N/2) + 1 (<= 15)"] = {B: choose(rel, wording_fam(B), B)
                                               for B in range(1, C + 1)}
final["current rule (rule_plan, no reset)"] = {B: tool_to_grid(H.rule_plan(B)) for B in range(1, C + 1)}
d = H.load_data()
fresh = {}
for i, c in enumerate(CASES):
    h = H.get_horse(d, c["horse"])
    g, b = c37.BOOSTS[c["boost"]]
    ev = F.Evaluator(h, h.M(H.training_bonus(c["training"]), g, b), max_budget=C, learned=c["learned"],
                     start_level=c["level"])
    keys = sorted({c37r.tool_plan(PLANS[j], c["level"]) for rule in final.values() for j in rule.values()
                   if j is not None})
    r = c37r.evaluate(ev, keys, 4000, 2002)
    for k in keys:
        fresh[(i, k)] = r[k]["full"]
    print(f"recheck {i + 1}/{len(CASES)}", flush=True)
lines += ["", "# Chosen on all reliable cases, rechecked with 4000 fresh horses per case: worst / average loss over the",
          "# reliable cases, worst over the Arduanatt cases (left out of the fit), and the worst case.",
          "budget\trule family\tplan\tworst\taverage\tArduanatt worst\tworst case"]
out = {}
for B in range(1, C + 1):
    for fam, rule in final.items():
        j = rule.get(B)
        if j is None:
            continue
        L = np.array([100 * (REF[i, B] - fresh[(i, c37r.tool_plan(PLANS[j], c["level"]))][B])
                      for i, c in enumerate(CASES)])
        lr, la = L[REL], L[~REL]
        wc = CASES[int(rel[np.argmax(lr)])]["label"]
        if B in BUDGETS:
            lines.append(f"{B}\t{fam}\t{describe(j, B)}\t{lr.max():.1f}\t{lr.mean():.1f}\t{la.max():.1f}\t{wc}")
        out.setdefault(str(B), {})[fam] = {"plan": list(c37r.tool_plan(PLANS[j], 1)), "worst": float(lr.max()),
                                           "avg": float(lr.mean()), "arduanatt_worst": float(la.max()), "worst_case": wc}
open(os.path.join(HERE, "c37r_rules.txt"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, "c37r_rules.json"), "w"))
print("\n".join(lines))
