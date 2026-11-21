"""C37r: C37 + C37b redone with the Skill Change Points reset, on the tool's fast engine (part 1: values).

Same 82 cases as C37 (c37.cases(): 4 horses x 6 Training levels x 3 boosts, plus 9 partway horses). One merged
plan grid (C37's and C37b's): V0 and V2 with every start level 2-29 and every spending cap 1-24 plus 26/30/35/40;
'V0 until T learned skills, then V2' (T 9-17) on the same grid; All at 30. Budgets 0..40.
Stage 1: 1000 horses per plan (seed 1, all plans of a case on the same horses). Reference best per case and budget:
the top 5 stage-1 plans of each budget rerun with 4000 fresh horses (seed 1001).
Saves c37r_cases/<i>.npz (vals: plan x budget, ref: budget) and c37r_cases/index.json, in C37's format (plans as
(code, start, cap, 0, T) with codes 0 at30, 1 V0, 6 V2, 12 switch). Resumable (skips saved cases).
Usage: python3 -I c37r.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE))), HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402
import c37                                                               # noqa: E402  (cases, boosts)

C = 40
OUT = os.path.join(HERE, "c37r_cases")
CAPS = list(range(1, 25)) + [26, 30, 35, 40]
TS = list(range(9, 18))
PLANS = ([(1, s, c, 0, 0) for s in range(2, 30) for c in CAPS] + [(6, s, c, 0, 0) for s in range(2, 30) for c in CAPS]
         + [(12, s, c, 0, T) for s in range(2, 30) for c in CAPS for T in TS] + [(0, 1, 0, 0, 0)])
NAME = {0: "at30", 1: "coursier", 6: "coursier_v2", 12: "coursier_switch"}
CHUNK = 1500


def tool_plan(p, level):
    st, s, cap, _, T = p
    return (NAME[st], max(s, level + 1) if st else 1, cap if st else 0, T)


def evaluate(ev, plans, runs, seed):
    out = {}
    for i in range(0, len(plans), CHUNK):
        out.update(ev.plans(plans[i:i + CHUNK], runs=runs, seed=seed))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    d = H.load_data()
    cs = c37.cases()
    json.dump({"cases": cs, "plans": PLANS, "C": C}, open(os.path.join(OUT, "index.json"), "w"))
    for i, c in enumerate(cs):
        f = os.path.join(OUT, f"{i}.npz")
        if os.path.exists(f):
            continue
        t0 = time.time()
        h = H.get_horse(d, c["horse"])
        g, b = c37.BOOSTS[c["boost"]]
        ev = F.Evaluator(h, h.M(H.training_bonus(c["training"]), g, b), max_budget=C, learned=c["learned"],
                         start_level=c["level"])
        keys = [tool_plan(p, c["level"]) for p in PLANS]
        r1 = evaluate(ev, sorted(set(keys)), 1000, 1)
        vals = np.array([[np.nan if x is None else x for x in r1[k]["full"]] for k in keys], np.float32)
        top = set()
        for B in range(C + 1):
            ok = np.where(~np.isnan(vals[:, B]))[0]
            top.update(keys[j] for j in ok[np.argsort(-vals[ok, B], kind="stable")[:5]])
        r2 = evaluate(ev, sorted(top), 4000, 1001)
        ref = np.full(C + 1, np.nan, np.float32)
        for B in range(C + 1):
            ok = np.where(~np.isnan(vals[:, B]))[0]
            js = ok[np.argsort(-vals[ok, B], kind="stable")[:5]]
            ref[B] = max(r2[keys[j]]["full"][B] for j in js)
        np.savez_compressed(f, vals=vals, ref=ref)
        print(f"{i + 1}/{len(cs)} {c['label']}: {time.time() - t0:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
