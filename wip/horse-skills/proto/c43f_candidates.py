"""C43 full version, part 3: hand-made candidate rules, checked with fresh horses (4000 per case, seed 5005) on both
target sets (c43f_courser, c43f_travel10; loss vs each case's reference best, points of the full-set chance).
The automatic wording search (c43f_rules.py) works on the noisy stage-1 values; these candidates come from reading
its output and the per-budget fits.
  A  current: bdo.horses.rule_plan (1: at30; 2-19 V2 from max(10, 31 - 1.75 N), keep 1; 20-21 from 11, V0 until 10,
     then V2, keep 1; 22+ from 10, V0 until 12, then V2, spend <= 24)
  B  A, but 2-6 coupons: V2 from 30 - 2 N (26, 24, 22, 20, 18), keep 1  (the courser fit starts earlier there)
  C  V2 up to 24 coupons (A's formula), then A's last band (from 10, V0 until 12, then V2, spend <= 24)
  D  C with B's small-budget starts
  E  C, but 25+: from 10, V0 until 13, then V2, spend <= 20 (the travel10 search's high band)
Output: c43f_candidates.txt. Usage: python3 -I c43f_candidates.py
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE))), HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
import c37r                                                              # noqa: E402
import c43                                                               # noqa: E402

C = 40


def v2f(N):
    return min(29, max(10, math.floor(31 - 1.75 * N + 0.5)))


def A(N):
    return H.rule_plan(N)


def B(N):
    return ("coursier_v2", 30 - 2 * N, N - 1, 0) if 2 <= N <= 6 else A(N)


def Cc(N):
    if N <= 1:
        return ("at30", 1, 0, 0)
    if N <= 24:
        return ("coursier_v2", v2f(N), N - 1, 0)
    return ("coursier_switch", 10, 24, 12)


def Dd(N):
    return ("coursier_v2", 30 - 2 * N, N - 1, 0) if 2 <= N <= 6 else Cc(N)


def E(N):
    return ("coursier_switch", 10, 20, 13) if N >= 25 else Cc(N)


RULES = {"A": A, "B": B, "C": Cc, "D": Dd, "E": E}


def run(name):
    D = os.path.join(HERE, f"c43f_{name}")
    ix = json.load(open(os.path.join(D, "index.json")))
    cases, wanted = ix["cases"], ix["wanted"]
    REF = np.stack([np.load(os.path.join(D, f"{i}.npz"))["ref"] for i in range(len(cases))])
    d = H.load_data()
    loss = {k: np.zeros((len(cases), C + 1)) for k in RULES}
    for i, c in enumerate(cases):
        ev = c43.evaluator(c, wanted, d)
        fix = lambda p: (p[0], max(p[1], c["level"] + 1) if p[0] != "at30" else 1, p[2], p[3])
        plans = {k: {N: fix(f(N)) for N in range(1, C + 1)} for k, f in RULES.items()}
        r = c37r.evaluate(ev, sorted({p for x in plans.values() for p in x.values()}), 4000, 5005)
        for k in RULES:
            for N in range(1, C + 1):
                loss[k][i, N] = 100 * (REF[i, N] - r[plans[k][N]]["full"][N])
        print(f"{name} {i + 1}/{len(cases)}", flush=True)
    return cases, loss


lines = ["# C43 candidates, fresh horses (4000 per case, seed 5005): worst / average loss per budget (points)"]
for name in ("courser", "travel10"):
    cases, loss = run(name)
    lines += ["", f"## {name} ({len(cases)} cases)", "N\t" + "\t".join(RULES)]
    for N in range(1, C + 1):
        lines.append(f"{N}\t" + "\t".join(f"{loss[k][:, N].max():.1f}/{loss[k][:, N].mean():.1f}" for k in RULES))
    lines.append("max 2-40\t" + "\t".join(f"{loss[k][:, 2:].max(0).max():.1f}" for k in RULES))
    lines.append("mean of worst 2-40\t" + "\t".join(f"{loss[k][:, 2:].max(0).mean():.2f}" for k in RULES))
open(os.path.join(HERE, "c43f_candidates.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
