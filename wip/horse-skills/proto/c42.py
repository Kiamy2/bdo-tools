"""C42 v0-order: does the order of the two V0 swaps matter, and does looping until neither fodder skill is held help?

Variants of V0 (also inside 'V0 until T learned skills, then V2'; the V2 phase is unchanged: it cycles the heavier
of Hind Kick / Fore Chop, Hind Kick on ties, as in the tool):
  A  once per level: Hind Kick (if held), then Fore Chop (if held)   [the tool's V0]
  B  once per level: Fore Chop, then Hind Kick
  C  loop: Hind Kick, Fore Chop, again, ... until neither is held (or the spending cap)
  D  loop: Fore Chop, Hind Kick, again, ...
Engine: v0order_fast.py (a generated copy of bdo/horses_fast.py with the loop codes; c42_make.py).
Cases: the 63 reliable C37r cases. Plans per variant: V0 and the switch, start levels 2, 5, ..., 29, spending caps
2-40 (12 values), T 9-15; plus the compact rule's plans (20-21: from 11, V0 until 10, keep 1; 22+: from 10, V0
until 12, spend <= 24). Stage 1: 1000 horses (seed 1, same for every variant); per variant, family (V0 / switch)
and budget, the top 3 are rerun with 4000 fresh horses (seed 5005) and the best is the variant's value. The rule's
plans are rerun with seed 5005 too. Results per case in c42_cases/<i>.json (resumable).
Usage: python3 -I c42.py; summary: python3 -I c42.py summary
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE))), HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
import c37                                                               # noqa: E402
import v0order_fast as F                                                 # noqa: E402

OUT = os.path.join(HERE, "c42_cases")
C = 40
BUDGETS = [10, 15, 20, 25, 30, 40]
STARTS = list(range(2, 30, 3))
CAPS = [2, 4, 6, 8, 10, 12, 15, 18, 21, 24, 30, 40]
TS = list(range(9, 16))
VARIANTS = {"A": (False, False), "B": (True, False), "C": (False, True), "D": (True, True)}   # (reversed, loop)


def rule(B):
    return ("coursier_switch", 11, B - 1, 10) if B <= 21 else ("coursier_switch", 10, min(24, B), 12)


def names(loop):
    return ("coursier_loop", "coursier_switch_loop") if loop else ("coursier", "coursier_switch")


def family_plans(loop):
    v0, sw = names(loop)
    return {"V0": [(v0, s, c, 0) for s in STARTS for c in CAPS],
            "switch": [(sw, s, c, T) for s in STARTS for c in CAPS for T in TS]}


def evaluator(h, M, c, rev):
    fod = list(reversed(H.CLASSIC_FODDER)) if rev else list(H.CLASSIC_FODDER)
    ev = F.Evaluator(h, M, max_budget=C, learned=c["learned"], start_level=c["level"], fodder=fod)
    ref = F.Evaluator(h, M, max_budget=C, learned=c["learned"], start_level=c["level"])
    m = list(ev.masks)
    m[3] = ref.masks[3]                                  # same V2 skill whatever the V0 order
    ev.masks = tuple(m)
    return ev


def fix(p, level):
    st, s, cap, T = p
    return (st, max(s, level + 1), cap, T)


def run():
    os.makedirs(OUT, exist_ok=True)
    idx = json.load(open(os.path.join(HERE, "c37r_cases", "index.json")))
    d = H.load_data()
    for i, c in enumerate(idx["cases"]):
        f = os.path.join(OUT, f"{i}.json")
        if not c["reliable"] or os.path.exists(f):
            continue
        t0 = time.time()
        h = H.get_horse(d, c["horse"])
        g, b = c37.BOOSTS[c["boost"]]
        M = h.M(H.training_bonus(c["training"]), g, b)
        res = {}
        for v, (rev, loop) in VARIANTS.items():
            ev = evaluator(h, M, c, rev)
            fam = {k: sorted({fix(p, c["level"]) for p in ps}) for k, ps in family_plans(loop).items()}
            r1 = {}
            allp = sorted(set(fam["V0"]) | set(fam["switch"]))
            for k in range(0, len(allp), 1500):
                r1.update(ev.plans(allp[k:k + 1500], runs=1000, seed=1))
            top = set()
            for k, ps in fam.items():
                for B in BUDGETS:
                    ok = [p for p in ps if r1[p]["full"][B] is not None]
                    top.update(sorted(ok, key=lambda p: -r1[p]["full"][B])[:3])
            rules = {fix((names(loop)[1],) + rule(B)[1:], c["level"]) for B in BUDGETS if B >= 20}
            r2 = ev.plans(sorted(top | rules), runs=4000, seed=5005)
            out = {}
            for k, ps in fam.items():
                for B in BUDGETS:
                    ok = [p for p in ps if r1[p]["full"][B] is not None]
                    t3 = sorted(ok, key=lambda p: -r1[p]["full"][B])[:3]
                    bp = max(t3, key=lambda p: r2[p]["full"][B])
                    out[f"{k}|{B}"] = [r2[bp]["full"][B], list(bp)]
            for B in BUDGETS:
                if B >= 20:
                    rp = fix((names(loop)[1],) + rule(B)[1:], c["level"])
                    out[f"rule|{B}"] = [r2[rp]["full"][B], list(rp)]
            res[v] = out
        json.dump({"case": c["label"], "res": res}, open(f, "w"))
        print(f"{i + 1}/{len(idx['cases'])} {c['label']}: {time.time() - t0:.0f}s", flush=True)
    print("done", flush=True)


def summary():
    rows = [json.load(open(os.path.join(OUT, f))) for f in sorted(os.listdir(OUT), key=lambda x: int(x[:-5]))]
    lines = [f"# C42 v0-order: {len(rows)} cases. Difference to A (tool's V0: once per level, Hind Kick then Fore "
             "Chop), points of the full-set chance (fresh horses): average [lowest, highest] over cases.",
             "# B = once, Fore Chop first; C = loop until neither held, Hind Kick first; D = loop, Fore Chop first.",
             "# family V0 / switch: each variant's best plan of the family (top 3 of stage 1 rechecked); rule: the "
             "compact rule's plan.", "", "family\tcoupons\tA\tB - A\tC - A\tD - A"]
    for k in ("V0", "switch", "rule"):
        for B in BUDGETS:
            key = f"{k}|{B}"
            if key not in rows[0]["res"]["A"]:
                continue
            a = np.array([r["res"]["A"][key][0] for r in rows])
            cells = [f"{100 * a.mean():.1f}%"]
            for v in "BCD":
                x = 100 * (np.array([r["res"][v][key][0] for r in rows]) - a)
                cells.append(f"{x.mean():+.2f} [{x.min():+.1f}, {x.max():+.1f}]")
            lines.append(f"{k}\t{B}\t" + "\t".join(cells))
    open(os.path.join(HERE, "c42_results.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    summary() if sys.argv[1:] == ["summary"] else run()
