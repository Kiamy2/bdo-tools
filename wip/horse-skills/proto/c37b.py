"""C37b band refinement (16-24 coupons), part 1 (same cases as C37): evaluate every plan in ~80 cases and save the values.

Cases: horses x Training levels x boosts (none / gear / both), plus horses partway through leveling.
Plans: V0 and V2 with every start level 2-29 and a grid of spending caps; 'V0 until T skills held, then V2'
(T 11-17) on the same grid. Stage 1: 1000 horses per plan (values for every budget 0..C). Reference best per case
and budget: the top 5 stage-1 plans of each budget rerun with 4000 fresh horses.
Saves c37_cases/<i>.npz (stage-1 values, reference best) and c37_cases/index.json. Resumable (skips saved cases).
Part 2 (c37_rules.py) fits and cross-validates the rules.
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
import c36_fast as X                                                     # noqa: E402

C = 24
OUT = os.path.join(HERE, "c37b_cases")
os.makedirs(OUT, exist_ok=True)
CAPS = list(range(1, 25))
TS = list(range(9, 17))
PLANS = ([(1, s, c, 0, 0) for s in range(2, 30) for c in CAPS] + [(6, s, c, 0, 0) for s in range(2, 30) for c in CAPS]
         + [(12, s, c, 0, T) for s in range(2, 30) for c in CAPS for T in TS] + [(0, 1, 0, 0, 0)])
HORSES = [("Mythical Diné", True), ("Doom (T9)", True), ("T8 example (bdolytics icon horse_71)", True),
          ("Mythical Arduanatt", False)]
TRAININGS = ["Beginner 1", "Skilled 1", "Professional 10", "Artisan 7", "Master 20", "Guru 20"]
BOOSTS = {"none": (0, 0), "gear": (1, 0), "both": (1, 1)}


def partway_states(h, M, level, n, seed):
    """Real states at 'level' from natural leveling (no coupons used): learned skill names."""
    rng = random.Random(seed)
    pool = list(h.weights)
    out = []
    for _ in range(n):
        have = set()
        for _lvl in range(1, level):
            un = [s for s in pool if s not in have]
            su = sum(h.weights[s] for s in un)
            k = min(M / (su + h.W), 1 / su)
            x = rng.random()
            for s in un:
                x -= k * h.weights[s]
                if x < 0:
                    have.add(s)
                    break
        out.append(sorted(have))
    return out


def cases():
    d = H.load_data()
    out = []
    for hn, reliable in HORSES:
        h = H.get_horse(d, hn)
        for tr in TRAININGS:
            for bn, (g, b) in BOOSTS.items():
                out.append(dict(label=f"{hn.split(' (')[0]} | {tr} | {bn}", horse=hn, training=tr, boost=bn,
                                reliable=reliable, learned=[], level=1))
        if reliable:                                   # partway horses (natural leveling so far, no coupon used)
            for tr, lv, sd in (("Skilled 1", 8, 1), ("Artisan 7", 8, 2), ("Artisan 7", 12, 3)):
                M = h.M(H.training_bonus(tr), 0, 0)
                learned = partway_states(h, M, lv, 1, sd)[0]
                out.append(dict(label=f"{hn.split(' (')[0]} | {tr} | none | level {lv}, {len(learned)} skills",
                                horse=hn, training=tr, boost="none", reliable=True, learned=learned, level=lv))
    return out


def main():
    d = H.load_data()
    cs = cases()
    json.dump({"cases": cs, "plans": PLANS, "C": C}, open(os.path.join(OUT, "index.json"), "w"))
    tables = {}
    for i, c in enumerate(cs):
        f = os.path.join(OUT, f"{i}.npz")
        if os.path.exists(f):
            continue
        t0 = time.time()
        h = H.get_horse(d, c["horse"])
        if c["horse"] not in tables:
            tables.clear()
        g, b = BOOSTS[c["boost"]]
        ev = X.Evaluator(h, h.M(H.training_bonus(c["training"]), g, b), C=C, table=tables.get(c["horse"]),
                         learned=c["learned"], start_level=c["level"])
        tables[c["horse"]] = ev.table
        vals = np.full((len(PLANS), C + 1), np.nan, np.float32)
        cache = {}
        for j, (st, s, cap, xa, xb) in enumerate(PLANS):
            s_eff = max(s, c["level"] + 1) if st else s            # a start level already passed means "start now"
            key = (st, s_eff, cap, xa, xb)
            if key not in cache:
                cache[key] = ev.plan(*key, runs=1000, seed=1)
            vals[j] = cache[key]
        ref = np.full(C + 1, np.nan, np.float32)
        for B in range(C + 1):
            ok = np.where(~np.isnan(vals[:, B]))[0]
            top = ok[np.argsort(-vals[ok, B])[:5]]
            best = 0.0
            for j in top:
                st, s, cap, xa, xb = PLANS[j]
                key = (st, max(s, c["level"] + 1) if st else s, cap, xa, xb)
                if ("ref", key) not in cache:
                    cache[("ref", key)] = ev.plan(*key, runs=4000, seed=1001)
                best = max(best, cache[("ref", key)][B])
            ref[B] = best
        np.savez_compressed(f, vals=vals, ref=ref)
        print(f"{i + 1}/{len(cs)} {c['label']}: {time.time() - t0:.0f}s, table {ev.table.rows} rows", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
