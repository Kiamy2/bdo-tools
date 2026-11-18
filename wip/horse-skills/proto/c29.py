"""C29 rerun-optimizer: level-1 plans with V2 and the exact cleanup.

For each scenario: every plan (at30; coursier and coursier_v2 with start level 2-29 and spending cap 1-40) with
RUNS1 simulated horses; then, for each budget and goal, the top plans and those close to the best are rerun with
RUNS2 fresh horses. Ties = within 1 point (full set) / 0.05 skill (travel skills) of the best, on the rerun.
Then the 'safest' plan per budget: smallest worst-case loss across F1 F2 F3 F5 F6 (stage-1 values), rechecked with
fresh horses in every scenario, and tested on F4 (left out of the choice).
Outputs: c29_<scenario>.txt, c29_safest.txt, c29.json.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                      # noqa: E402
from bdo import horses as H                                             # noqa: E402
import table_nb as T                                                    # noqa: E402

C = 40
RUNS1, RUNS2, RUNS3 = 1000, 4000, 8000
FAM = ["coursier", "coursier_v2"]
NAMES = {"at30": "All at 30", "coursier": "plain Coursier", "coursier_v2": "V2"}
SC = {  # least to most favourable
    "F1": dict(horse="T8 example (bdolytics icon horse_71)", training=16.8, label="T8, Professional 10"),
    "F2": dict(horse="Mythical Diné", training=21.7, label="Diné, Artisan 7"),
    "F3": dict(horse="Doom (T9)", training=21.7, label="T9 Doom, Artisan 7"),
    "F4": dict(horse="Mythical Diné", training=21.7, start_level=2, learned=["High Jump"], points=1, tickets=4,
               label="user's Diné as of 2026-11-17 (level 2, High Jump, 1 point, 4 tickets)"),
    "F5": dict(horse="Mythical Diné", training=21.7, gear=1, brand=1, label="Diné, Artisan 7, both boosts"),
    "F6": dict(horse="Mythical Diné", training=100, label="Diné, Guru 20"),
    "F4now": dict(horse="Mythical Diné", training=21.7, start_level=4, learned=["High Jump", "Quick Back", "Roar"],
                  points=2, tickets=4, label="user's Diné now (level 4, High Jump + Quick Back + Roar, 2 points, 4 tickets)"),
}
PLANS = [("at30", 1, 0)] + [(f, L, cap) for f in FAM for L in range(2, 30) for cap in range(1, C + 1)]
d = H.load_data()
tables = {}


def evaluator(sc):
    s = SC[sc]
    h = H.get_horse(d, s["horse"])
    key = (s["horse"], s.get("points", 0))
    ev = T.Evaluator(h, h.M(s["training"], s.get("gear", 0), s.get("brand", 0)), table=tables.get(key),
                     max_budget=C, learned=s.get("learned", ()), points=s.get("points", 0),
                     tickets=s.get("tickets", 0), start_level=s.get("start_level", 1))
    tables[key] = ev.table
    return ev


def valid(plan, sc):
    return plan[0] == "at30" or plan[1] > SC[sc].get("start_level", 1)


def span(v):
    return f"{v[0]}" if v[0] == v[-1] else f"{v[0]}-{v[-1]}"


def describe(tied, B):
    out = []
    for f in ["at30"] + FAM:
        ps = [p for p in tied if p[0] == f]
        if not ps:
            continue
        if f == "at30":
            out.append("All at 30")
            continue
        out.append(f"{NAMES[f]} from lvl {span(sorted({p[1] for p in ps}))}, keep {span(sorted({B - p[2] for p in ps}))}")
    return " | ".join(out)


results = {}
stage1 = {}
for sc in SC:
    t0 = time.time()
    ev = evaluator(sc)
    plans = [p for p in PLANS if valid(p, sc)]
    s1 = {p: ev.plan(*p, runs=RUNS1, seed=1) for p in plans}
    stage1[sc] = s1
    keep = {("at30", 1, 0)}
    for B in range(C + 1):
        for goal, margin in (("full", 0.025), ("wanted", 0.08)):
            ok = [p for p in plans if s1[p][goal][B] is not None]
            ranked = sorted(ok, key=lambda p: -s1[p][goal][B])
            keep.update(ranked[:6])
            keep.update([p for p in ranked if s1[p][goal][B] >= s1[ranked[0]][goal][B] - margin][:25])
    s2 = {p: ev.plan(*p, runs=RUNS2, seed=1001) for p in keep}
    lines = [f"# C29 rerun-optimizer: {sc} = {SC[sc]['label']}",
             f"# plans: All at 30; plain Coursier and V2 (cycle Hind Kick, keep Fore Chop) from every start level "
             f"and spending cap; exact level-30 cleanup (rarest unwanted first, rarest missing as desired)",
             f"# {len(plans)} plans x {RUNS1} horses, then {len(keep)} plans x {RUNS2} fresh horses. Ties: within 1 point "
             f"(full set) / 0.05 skill (travel skills). 'from lvl' = level to start swapping, 'keep' = coupons kept for "
             f"level 30.",
             "coupons\tfull set: best\ttied plans\ttravel skills: best\ttied plans\tAll at 30: full set, travel skills"]
    best_full = []
    at = s2[("at30", 1, 0)]
    for B in range(C + 1):
        ok = [p for p in s2 if s2[p]["full"][B] is not None]
        bf = max(s2[p]["full"][B] for p in ok)
        tf = [p for p in ok if s2[p]["full"][B] >= bf - 0.01]
        bw = max(s2[p]["wanted"][B] for p in ok)
        tw = [p for p in ok if s2[p]["wanted"][B] >= bw - 0.05]
        best_full.append(bf)
        lines.append(f"{B}\t{100 * bf:.1f}%\t{describe(tf, B)}\t{bw:.2f}\t{describe(tw, B)}\t"
                     f"{100 * at['full'][B]:.1f}%, {at['wanted'][B]:.2f}")
    need = {}
    for t in (0.5, 0.8, 0.9, 0.95):
        b = next((B for B, x in enumerate(best_full) if x >= t), None)
        b30 = next((B for B, x in enumerate(at["full"]) if x >= t), None)
        need[t] = (b, b30)
        lines.append(f"# coupons for a {t:.0%} chance of the full set: {b if b is not None else '> 40'} with the best "
                     f"plan, {b30 if b30 is not None else '> 40'} with All at 30")
    open(os.path.join(HERE, f"c29_{sc}.txt"), "w").write("\n".join(lines) + "\n")
    results[sc] = {"best_full": best_full, "need": {str(k): v for k, v in need.items()},
                   "at30_full": at["full"], "rows": lines[4:]}
    print(f"{sc} done in {time.time() - t0:.0f}s ({len(keep)} plans rechecked)", flush=True)
    if sc in ("F3",):                       # different horse next: free memory of tables no longer needed
        for k in [k for k in tables if k[0] == "Doom (T9)"]:
            del tables[k]
    if sc == "F1":
        for k in [k for k in tables if k[0].startswith("T8")]:
            del tables[k]

# safest plan per budget across the report scenarios (F4 left out)
REP = ["F1", "F2", "F3", "F5", "F6"]
lines = ["# C29: safest single plan per budget = smallest worst-case loss across F1 F2 F3 F5 F6 (loss = scenario's",
         "# best chance minus this plan's chance, in points of the full-set chance). Chosen on stage-1 values, then",
         f"# rechecked with {RUNS3} fresh horses per scenario; F4 (the user's Diné) was left out of the choice.",
         "coupons\tsafest plan\tworst loss\taverage loss\tloss F1 F2 F3 F5 F6\tloss on F4 (held out)\tAll at 30 worst / average loss"]
safest = {}
evs = {}
for B in range(1, C + 1):
    ok = [p for p in PLANS if all(stage1[sc].get(p) and stage1[sc][p]["full"][B] is not None for sc in REP)]
    best1 = {sc: max(stage1[sc][p]["full"][B] for p in ok) for sc in REP}
    ranked = sorted(ok, key=lambda p: max(best1[sc] - stage1[sc][p]["full"][B] for sc in REP))[:8]
    safest[B] = ranked
cand = sorted({p for B in safest for p in safest[B]})
fresh = {sc: {} for sc in REP + ["F4"]}
for sc in REP + ["F4"]:
    ev = evaluator(sc)
    for p in cand:
        if valid(p, sc):
            fresh[sc][p] = ev.plan(*p, runs=RUNS3, seed=2002)["full"]
    if sc == "F1":
        for k in [k for k in tables if k[0].startswith("T8")]:
            del tables[k]
    if sc == "F3":
        for k in [k for k in tables if k[0] == "Doom (T9)"]:
            del tables[k]
out_safest = {}
for B in range(1, C + 1):
    ref = {sc: results[sc]["best_full"][B] for sc in REP + ["F4"]}
    loss = {p: {sc: 100 * (ref[sc] - fresh[sc][p][B]) for sc in REP} for p in safest[B]}
    p = min(loss, key=lambda q: (max(loss[q].values()), sum(loss[q].values())))
    l4 = 100 * (ref["F4"] - fresh["F4"][p][B]) if p in fresh["F4"] else float("nan")
    a30 = [100 * (ref[sc] - results[sc]["at30_full"][B]) for sc in REP]
    name = "All at 30" if p[0] == "at30" else f"{NAMES[p[0]]} from lvl {p[1]}, keep {B - p[2]}"
    lines.append(f"{B}\t{name}\t{max(loss[p].values()):.1f}\t{sum(loss[p].values()) / 5:.1f}\t"
                 + " ".join(f"{loss[p][sc]:.1f}" for sc in REP) + f"\t{l4:.1f}\t{max(a30):.1f} / {sum(a30) / 5:.1f}")
    out_safest[B] = {"plan": p, "worst": max(loss[p].values()), "avg": sum(loss[p].values()) / 5, "F4": l4}
open(os.path.join(HERE, "c29_safest.txt"), "w").write("\n".join(lines) + "\n")
json.dump({"scenarios": results, "safest": {str(k): v for k, v in out_safest.items()}},
          open(os.path.join(HERE, "c29.json"), "w"))
print("safest done", flush=True)
