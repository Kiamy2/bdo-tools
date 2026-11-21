"""C43 rules per use case (part 1: values), with the points reset, on the tool's fast engine. Same method as C37r.

  courser: default T8 types (Sprint the only innate skill), target = the courser set (bdo.horses.COURSER_SET);
           types 1, 2, 3, 4, 5, 19, 20, 22 (one per distinct weight / 'no skill' profile), 6 Training levels x
           3 boosts, + 4 partway horses.
  travel10: T10s (Mythical Diné, Mythical Doom, Mythical Arduanatt; the user: Arduanatt included), target =
           the travel set, 6 Training levels x 3 boosts, + 6 partway horses.
Plans (to keep the run near 1 h): V0 / V2 / 'V0 until T, then V2' (T 9-17) with start levels 2-29 and C37's
coarser cap grid (1-4, 6, 8, 10, 12, 15, 18, 22, 26, 30, 35, 40), + the compact travel rule's plans for every budget,
+ All at 30 (about 4660 plans; budgets 0..40). courser: Type 20 left out (as 19 / 22 apart from S: Instant Accel), and
boosts none / gear + brand only. Stage 1: 1000 horses per plan (seed 1); reference best per
budget: the top 5 rerun with 4000 fresh horses (seed 1001). Saves c43_<set>/<i>.npz (+ index.json), resumable.
Usage: python3 -I c43.py courser|travel10
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
import c37                                                               # noqa: E402  (partway_states, BOOSTS)
import c37r                                                              # noqa: E402  (PLANS, tool_plan, evaluate)

C = 40
TRAININGS = ["Beginner 1", "Skilled 1", "Professional 10", "Artisan 7", "Master 20", "Guru 20"]
SETS = {
    "courser": dict(wanted=H.COURSER_SET,
                    horses=["T8 Type 1", "T8 Type 2", "T8 Type 3", "T8 Type 4", "T8 Type 5", "T8 Type 19", "T8 Type 22"],
                    boosts=["none", "both"],
                    partway=[("T8 Type 1", "Artisan 7", 8, 1), ("T8 Type 1", "Artisan 7", 12, 2),
                             ("T8 Type 5", "Skilled 1", 8, 3), ("T8 Type 19", "Artisan 7", 12, 4)]),
    "travel10": dict(wanted=H.TRAVEL_SET,
                     horses=["Mythical Diné", "Mythical Doom", "Mythical Arduanatt"], boosts=["none", "gear", "both"],
                     partway=[(h, tr, lv, sd) for h in ("Mythical Diné", "Mythical Doom")
                              for tr, lv, sd in (("Skilled 1", 8, 1), ("Artisan 7", 8, 2), ("Artisan 7", 12, 3))]),
}


CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30, 35, 40]
CODE = {"at30": 0, "coursier": 1, "coursier_v2": 6, "coursier_switch": 12}
PLANS = sorted(set([(st, s, c, 0, 0) for st in (1, 6) for s in range(2, 30) for c in CAPS]
                   + [(12, s, c, 0, T) for s in range(2, 30) for c in CAPS for T in c37r.TS] + [(0, 1, 0, 0, 0)]
                   + [(CODE[p[0]], p[1], p[2], 0, p[3]) for p in (H.rule_plan(B) for B in range(1, 41))]))


def cases(name):
    d = H.load_data()
    s = SETS[name]
    out = [dict(label=f"{hn} | {tr} | {bn}", horse=hn, training=tr, boost=bn, reliable=True, learned=[], level=1)
           for hn in s["horses"] for tr in TRAININGS for bn in s["boosts"]]
    for hn, tr, lv, sd in s["partway"]:
        h = H.get_horse(d, hn)
        learned = c37.partway_states(h, h.M(H.training_bonus(tr), 0, 0), lv, 1, sd)[0]
        out.append(dict(label=f"{hn} | {tr} | none | level {lv}, {len(learned)} skills", horse=hn, training=tr,
                        boost="none", reliable=True, learned=learned, level=lv))
    return out


def evaluator(c, wanted, d=None):
    d = d or H.load_data()
    h = H.get_horse(d, c["horse"])
    g, b = c37.BOOSTS[c["boost"]]
    return F.Evaluator(h, h.M(H.training_bonus(c["training"]), g, b), max_budget=C, learned=c["learned"],
                       start_level=c["level"], wanted=wanted)


def main(name, limit=None):
    out = os.path.join(HERE, f"c43_{name}")
    os.makedirs(out, exist_ok=True)
    cs = cases(name)
    json.dump({"cases": cs, "plans": PLANS, "C": C, "wanted": SETS[name]["wanted"]},
              open(os.path.join(out, "index.json"), "w"), ensure_ascii=False)
    d = H.load_data()
    for i, c in enumerate(cs[:limit]):
        f = os.path.join(out, f"{i}.npz")
        if os.path.exists(f):
            continue
        t0 = time.time()
        ev = evaluator(c, SETS[name]["wanted"], d)
        keys = [c37r.tool_plan(p, c["level"]) for p in PLANS]
        r1 = c37r.evaluate(ev, sorted(set(keys)), 1000, 1)
        vals = np.array([[np.nan if x is None else x for x in r1[k]["full"]] for k in keys], np.float32)
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
        print(f"{i + 1}/{len(cs)} {c['label']}: {time.time() - t0:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
