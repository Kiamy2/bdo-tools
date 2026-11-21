"""C4r: C4 (bad outcomes; do near-equal plans differ in them?) redone with the points reset, on the tool's fast
engine (exact cleanup with tails), and with the new compact rule.

Per case and budget: full-set chance, chance of missing at most 1..4 wanted skills, average missing. Picks (stage 1:
1000 horses per plan, seed 4001, all plans on the same horses), then rerun with 4000 fresh horses (seed 4002):
  rule   the tool's general rule (bdo.horses.rule_plan, the compact rule)
  full   best full-set chance
  safe1  best chance of missing at most 1, among plans within 1 point of the best full-set chance
  safe2  same, missing at most 2
  mean   fewest missing on average (any plan)
Plans: All at 30; V0 and V2 with every start level 2-29 and caps 1-30 (13 values); 'V0 until T, then V2' (T 9-16)
on the same grid; plus the rule's plan. Cases: Diné, Doom, T8 x Beginner 1 / Skilled 1 / Artisan 7 / Guru 20, no
boosts. Budgets 10-30. Results: c4r_cases/<i>.json (resumable); summary: python3 -I c4r.py summary.
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

C = 30
BUDGETS = [10, 15, 20, 25, 30]
OUT = os.path.join(HERE, "c4r_cases")
CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30]
TS = list(range(9, 17))
PLANS = ([("at30", 1, 0, 0)] + [(st, s, c, 0) for st in ("coursier", "coursier_v2") for s in range(2, 30) for c in CAPS]
         + [("coursier_switch", s, c, T) for s in range(2, 30) for c in CAPS for T in TS])
HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAININGS = ["Beginner 1", "Skilled 1", "Artisan 7", "Guru 20"]


def row(r, B, nW):
    t = r["tails"][B]
    return [t[0], t[1], t[2], t[3], t[4], nW - r["wanted"][B]]


def run():
    os.makedirs(OUT, exist_ok=True)
    d = H.load_data()
    i = 0
    for hn in HORSES:
        h = H.get_horse(d, hn)
        for tr in TRAININGS:
            f = os.path.join(OUT, f"{i}.json")
            i += 1
            if os.path.exists(f):
                continue
            t0 = time.time()
            ev = F.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), max_budget=C)
            nW = len(set(H.TRAVEL_SET) & set(h.weights))
            plans = sorted(set(PLANS) | {H.rule_plan(B) for B in BUDGETS})
            r1 = {}
            for k in range(0, len(plans), 1200):
                r1.update(ev.plans(plans[k:k + 1200], runs=1000, seed=4001, tails=True))
            res = {"horse": hn, "training": tr, "budgets": {}}
            chosen_all = {}
            for B in BUDGETS:
                ok = [p for p in plans if r1[p]["full"][B] is not None]
                v = {p: row(r1[p], B, nW) for p in ok}
                best = max(v[p][0] for p in ok)
                near = [p for p in ok if v[p][0] >= best - 0.01]
                chosen_all[B] = {"rule": H.rule_plan(B), "full": max(ok, key=lambda p: v[p][0]),
                                 "safe1": max(near, key=lambda p: v[p][1]), "safe2": max(near, key=lambda p: v[p][2]),
                                 "mean": min(ok, key=lambda p: v[p][5])}
            r2 = ev.plans(sorted({p for c in chosen_all.values() for p in c.values()}), runs=4000, seed=4002,
                          tails=True)
            for B, ch in chosen_all.items():
                res["budgets"][B] = {k: {"plan": list(p), "stage1": [round(x, 5) for x in row(r1[p], B, nW)],
                                         "check": [round(x, 5) for x in row(r2[p], B, nW)]} for k, p in ch.items()}
            res["secs"] = round(time.time() - t0)
            json.dump(res, open(f, "w"), indent=1)
            print(f"{i}/{len(HORSES) * len(TRAININGS)} {hn} {tr}: {res['secs']}s", flush=True)
    print("done", flush=True)


def w95(c):
    for k in range(5):
        if c[k] >= 0.95:
            return str(k)
    return "5+"


def summary():
    rows = [json.load(open(os.path.join(OUT, f"{i}.json"))) for i in range(12)]
    L = ["# C4r (points reset): full set % | missing <= 1 % | missing <= 2 % | average missing | 95% of horses miss at "
         "most (4000 fresh horses)", ""]
    agg = {k: [] for k in ("rule", "safe1", "safe2", "mean")}
    for r in rows:
        L.append(f"## {r['horse'].split(' (')[0]} | {r['training']}")
        for B, d in r["budgets"].items():
            for k, x in d.items():
                c = x["check"]
                L.append(f"  {B} {k:5s} {100 * c[0]:5.1f} {100 * c[1]:5.1f} {100 * c[2]:5.1f} {c[5]:5.2f}  {w95(c):2s} "
                         f"{H.plan_name(tuple(x['plan']), int(B))}")
            f = d["full"]["check"]
            for k in agg:
                c = d[k]["check"]
                agg[k].append((100 * (c[0] - f[0]), 100 * (c[1] - f[1]), 100 * (c[2] - f[2]), c[5] - f[5],
                               f"{r['horse'].split(' (')[0]} {r['training']} {B}"))
    L += ["", "# Against 'full' (best full-set plan), rechecked: full set / <=1 / <=2 points, average missing; "
          "lowest and highest over the 60 case-budgets, and where"]
    for k, xs in agg.items():
        a = np.array([x[:4] for x in xs])
        L.append(f"{k:5s} full set {a[:, 0].min():+.1f}..{a[:, 0].max():+.1f} | <=1 {a[:, 1].min():+.1f}..{a[:, 1].max():+.1f}"
                 f" (largest at {xs[int(a[:, 1].argmax())][4]}) | <=2 {a[:, 2].min():+.1f}..{a[:, 2].max():+.1f} | "
                 f"avg missing {a[:, 3].min():+.3f}..{a[:, 3].max():+.3f}")
    open(os.path.join(HERE, "c4r_summary.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[-6:]))


if __name__ == "__main__":
    summary() if sys.argv[1:] == ["summary"] else run()
