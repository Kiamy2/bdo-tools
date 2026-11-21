"""C37r S2: does splitting the rule by scenario help? From the stored C37r values (c37r_cases).

Groupings of the 72 reliable cases (Arduanatt kept aside, as in C37):
  difficulty: by the case's best full-set chance with 20 coupons (reference), in thirds: hard / medium / easy;
  training: Beginner 1 + Skilled 1 / Professional 10 + Artisan 7 / Master 20 + Guru 20 (known to the player);
  horse: Diné (T10) / Doom (T9) / T8.
Per budget, 'single' = one plan for all cases (smallest worst-case loss over the fitting cases, then average),
'split' = one plan per group, chosen the same way within the group. 2-fold cross-validation, split within each
group, 5 random splits: chosen on one half, loss measured on the other half (stage-1 values vs the reference).
Then, chosen on all reliable cases, both rechecked with 4000 fresh horses per case (seed 4004).
Output: c37r_split.txt, c37r_split.json. Usage: python3 -I c37r_split.py
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
V = np.stack([np.load(os.path.join(D, f"{i}.npz"))["vals"] for i in range(len(CASES))])
REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(CASES))])
LOSS = 100 * (REF[:, None, :] - V)
rel = np.where([c["reliable"] for c in CASES])[0]
BUDGETS = list(range(2, C + 1))

d20 = REF[rel, 20]
q1, q2 = np.quantile(d20, [1 / 3, 2 / 3])
TRB = {"Beginner 1": "Beginner/Skilled", "Skilled 1": "Beginner/Skilled", "Professional 10": "Professional/Artisan",
       "Artisan 7": "Professional/Artisan", "Master 20": "Master/Guru", "Guru 20": "Master/Guru"}
GROUPINGS = {
    "difficulty": {i: ("hard" if REF[i, 20] < q1 else "medium" if REF[i, 20] < q2 else "easy") for i in rel},
    "training": {i: TRB[CASES[i]["training"]] for i in rel},
    "horse": {i: CASES[i]["horse"].split(" (")[0] for i in rel},
}


def choose(cases, B):
    L = LOSS[np.ix_(cases, np.arange(len(PLANS)), [B])][:, :, 0]
    ok = ~np.isnan(L).any(0)
    w, a = np.where(ok, L.max(0), np.inf), np.where(ok, L.mean(0), np.inf)
    return int(np.lexsort((a, np.round(w, 2)))[0])


rng = np.random.default_rng(11)
lines = [f"# C37r S2: one rule vs one rule per group. Difficulty thirds by best chance at 20 coupons: hard < "
         f"{100 * q1:.1f}% <= medium < {100 * q2:.1f}% <= easy.", ""]
out = {"thresholds_20": [float(q1), float(q2)], "groupings": {}}
final = {}
for gname, grp in GROUPINGS.items():
    names = sorted(set(grp.values()))
    members = {g: np.array([i for i in rel if grp[i] == g]) for g in names}
    cv = {(g, k): {B: [] for B in BUDGETS} for g in names for k in ("single", "split")}
    for split in range(5):
        halves = ([], [])
        for g in names:
            p = rng.permutation(members[g])
            halves[0].extend(p[: len(p) // 2]); halves[1].extend(p[len(p) // 2:])
        for a, b in ((0, 1), (1, 0)):
            fit, test = np.array(halves[a]), np.array(halves[b])
            for B in BUDGETS:
                js = choose(fit, B)
                for g in names:
                    tg = test[[grp[i] == g for i in test]]
                    jg = choose(fit[[grp[i] == g for i in fit]], B)
                    cv[(g, "single")][B].append(LOSS[tg, js, B])
                    cv[(g, "split")][B].append(LOSS[tg, jg, B])
    lines.append(f"## grouping by {gname}: held-out worst loss / average loss (points), single rule vs per-group rule")
    lines.append("group (cases)\trule\t" + "\t".join(str(B) for B in BUDGETS))
    for g in names:
        for k in ("single", "split"):
            cells = [f"{np.concatenate(cv[(g, k)][B]).max():.1f}/{np.concatenate(cv[(g, k)][B]).mean():.1f}"
                     for B in BUDGETS]
            lines.append(f"{g} ({len(members[g])})\t{k}\t" + "\t".join(cells))
    lines.append("")
    final[gname] = {g: {B: choose(members[g], B) for B in BUDGETS} for g in names}
    out["groupings"][gname] = {g: [int(i) for i in members[g]] for g in names}
single = {B: choose(rel, B) for B in BUDGETS}

d = H.load_data()
fresh = {}
for i in rel:
    c = CASES[i]
    h = H.get_horse(d, c["horse"])
    gg, bb = c37.BOOSTS[c["boost"]]
    ev = F.Evaluator(h, h.M(H.training_bonus(c["training"]), gg, bb), max_budget=C, learned=c["learned"],
                     start_level=c["level"])
    js = set(single.values())
    for gname, grp in GROUPINGS.items():
        js.update(final[gname][grp[i]].values())
    keys = sorted({c37r.tool_plan(PLANS[j], c["level"]) for j in js})
    r = c37r.evaluate(ev, keys, 4000, 4004)
    for k in keys:
        fresh[(int(i), k)] = r[k]["full"]
    print(f"recheck {list(rel).index(i) + 1}/{len(rel)}", flush=True)


def lossf(i, j, B):
    return 100 * (REF[i, B] - fresh[(int(i), c37r.tool_plan(PLANS[j], CASES[i]["level"]))][B])


lines.append("## rechecked with 4000 fresh horses (seed 4004): worst / average loss per group, single rule vs per-group "
             "rule (chosen on all reliable cases)")
for gname, grp in GROUPINGS.items():
    names = sorted(set(grp.values()))
    lines.append(f"# {gname}")
    lines.append("group\trule\t" + "\t".join(str(B) for B in BUDGETS))
    out[gname] = {}
    for g in names:
        mem = [i for i in rel if grp[i] == g]
        for k in ("single", "split"):
            cells, vals = [], []
            for B in BUDGETS:
                j = single[B] if k == "single" else final[gname][g][B]
                Lc = np.array([lossf(i, j, B) for i in mem])
                cells.append(f"{Lc.max():.1f}/{Lc.mean():.1f}")
                vals.append([float(Lc.max()), float(Lc.mean()), list(c37r.tool_plan(PLANS[j], 1))])
            lines.append(f"{g}\t{k}\t" + "\t".join(cells))
            out[gname].setdefault(g, {})[k] = vals
open(os.path.join(HERE, "c37r_split.txt"), "w").write("\n".join(lines) + "\n")
json.dump(out, open(os.path.join(HERE, "c37r_split.json"), "w"))
print("\n".join(lines[:4]))
