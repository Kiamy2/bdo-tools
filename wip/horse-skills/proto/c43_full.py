"""C43 full version (part 1: values): extends the first batch (c43_<set>/, coarse cap grid) to C37r's full grid
(every cap 1-24 + 26 / 30 / 35 / 40; 8625 plans) and the full case list:
  courser: types 1, 2, 3, 4, 5, 19, 20, 22 x 6 Training levels x 3 boosts (none / gear / gear + brand) + 4 partway;
  travel10: as in the first batch (60 cases).
A case of the first batch keeps its stage-1 values (1000 horses, seed 1: every plan is played on the same horses,
whatever batch it is evaluated in) and only the missing plans are added; new cases are computed in full. The
reference best per budget is recomputed over the full grid (top 5 rerun with 4000 fresh horses, seed 1001).
Check: the first extended case re-evaluates 50 first-batch plans and must reproduce them exactly.
Saves c43f_<set>/<i>.npz (+ index.json), resumable. Usage: python3 -I c43_full.py courser|travel10
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
import c37r                                                              # noqa: E402
import c43                                                               # noqa: E402

C = 40
PLANS = c37r.PLANS
FULL = {"courser": dict(c43.SETS["courser"], boosts=["none", "gear", "both"],
                        horses=["T8 Type 1", "T8 Type 2", "T8 Type 3", "T8 Type 4", "T8 Type 5", "T8 Type 19",
                                "T8 Type 20", "T8 Type 22"]),
        "travel10": c43.SETS["travel10"]}


def main(name):
    c43.SETS[name] = FULL[name]                          # c43.cases() reads the horse / boost lists from there
    cs = c43.cases(name)
    wanted = FULL[name]["wanted"]
    out = os.path.join(HERE, f"c43f_{name}")
    os.makedirs(out, exist_ok=True)
    json.dump({"cases": cs, "plans": PLANS, "C": C, "wanted": wanted}, open(os.path.join(out, "index.json"), "w"),
              ensure_ascii=False)
    old_dir = os.path.join(HERE, f"c43_{name}")
    old_ix = json.load(open(os.path.join(old_dir, "index.json")))
    old_plans = [tuple(p) for p in old_ix["plans"]]
    old_by_label = {c["label"]: i for i, c in enumerate(old_ix["cases"])}
    d = H.load_data()
    checked = False
    for i, c in enumerate(cs):
        f = os.path.join(out, f"{i}.npz")
        if os.path.exists(f):
            continue
        t0 = time.time()
        ev = c43.evaluator(c, wanted, d)
        keys = [c37r.tool_plan(p, c["level"]) for p in PLANS]
        known = {}
        if c["label"] in old_by_label:
            ov = np.load(os.path.join(old_dir, f"{old_by_label[c['label']]}.npz"))["vals"]
            for j, p in enumerate(old_plans):
                known[c37r.tool_plan(p, c["level"])] = ov[j]
        todo = sorted(set(keys) - set(known))
        r1 = c37r.evaluate(ev, todo, 1000, 1)
        if known and not checked:
            sample = sorted(known)[::max(1, len(known) // 50)][:50]
            rr = c37r.evaluate(ev, sample, 1000, 1)
            diff = max(np.nanmax(np.abs(np.array([np.nan if x is None else x for x in rr[k]["full"]], np.float32)
                                        - known[k])) for k in sample)
            print(f"check: {len(sample)} first-batch plans re-evaluated, largest difference {diff:.2e}", flush=True)
            if diff > 1e-6:
                sys.exit("first-batch values not reproduced: stop")
            checked = True
        vals = np.array([known[k] if k in known else [np.nan if x is None else x for x in r1[k]["full"]]
                         for k in keys], np.float32)
        top = set()
        for B in range(C + 1):
            ok = np.where(~np.isnan(vals[:, B]))[0]
            top.update(keys[j] for j in ok[np.argsort(-vals[ok, B], kind="stable")[:5]])
        r2 = c37r.evaluate(ev, sorted(top), 4000, 1001)
        ref = np.full(C + 1, np.nan, np.float32)
        for B in range(C + 1):
            ok = np.where(~np.isnan(vals[:, B]))[0]
            js = ok[np.argsort(-vals[ok, B], kind="stable")[:5]]
            ref[B] = max(r2[keys[j]]["full"][B] for j in js)
        np.savez_compressed(f, vals=vals, ref=ref)
        print(f"{i + 1}/{len(cs)} {c['label']} ({'extended' if known else 'new'}): {time.time() - t0:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
