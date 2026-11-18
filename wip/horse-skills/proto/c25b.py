"""C25b: does the best leveling plan change when a Selection Coupon is planned for the end?

Goal with the coupon: the full set using it at the end, with the cleanup keeping the rarest missing skill for it
(c25 'end2'); horses with fewer learned skills than wanted ones can't use it. For each case (c25's 12) and budget:
every plan of the C37 grid with 1000 horses, then the top 10 and the rule's plan (bdo.horses.rule_plan) rerun with
4000 fresh horses. Reports the gain of the best plan over the rule's plan, and what the best plans look like.

Usage: python3 -I c25b.py   (writes c25b_results.json, prints the summary)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402
from bdo.horses_fast import _pop, PBITS                                  # noqa: E402
import c25                                                               # noqa: E402

CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30]
PLANS = ([("at30", 1, 0, 0)] + [(st, s, c, 0) for st in ("coursier", "coursier_v2") for s in range(2, 30) for c in CAPS]
         + [("coursier_switch", s, c, T) for s in range(2, 30) for c in CAPS for T in H.SWITCH_TS])
C, RUNS1, RUNS2, TOP = 30, 1000, 4000, 10


def goal_values(plans, ev, runs, seed, g, nW):
    """[plan][B]: chance of the full set with the Selection Coupon at the end (end2 cleanup), B = 0..C."""
    w, n, W, M = ev.args
    lmask, wmask, fod, cyc, order, rare = ev.masks
    hk, hb, hp, hc = [], [], [], []
    for i, (st, lv, cap, T) in enumerate(plans):
        S, b, pts = F._many30(runs, seed, w, n, W, M, F.CODES[st], lv, cap if st != "at30" else 0, 0, 1, lmask,
                              wmask, fod, cyc, order, rare, 0.25, 0, 30, T)
        hk.append((S << PBITS) | pts)
        hb.append(b)
        hp.append(np.full(runs, i, np.int64))
        hc.append(np.full(runs, cap if st != "at30" else 0, np.int64))
    hk, hb, hp, hc = map(np.concatenate, (hk, hb, hp, hc))
    spare = F._popcounts(hk >> PBITS) >= nW
    hp = np.where(spare, hp, len(plans))                       # no spare skill: can't reach the full set
    acc = c25.le1_values(hk, hb, hp, hc, len(plans) + 1, C, g, True)[:len(plans)] / runs
    caps = np.array([0 if p[0] == "at30" else p[2] for p in plans])
    acc[np.arange(C + 1)[None, :] < caps[:, None]] = np.nan    # budget below the plan's spending cap
    return acc


def main():
    d = H.load_data()
    out = []
    for hn in c25.HORSES:
        h = H.get_horse(d, hn)
        for tr in c25.TRAININGS:
            t0 = time.time()
            ev = F.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), max_budget=C)
            w, n, W, M = ev.args
            lmask, wmask, fod, cyc, order, rare = ev.masks
            g, nW = (w, n, wmask, order, rare), _pop(int(wmask))
            v1 = goal_values(PLANS, ev, RUNS1, 4101, g, nW)
            row = {"horse": hn, "training": tr, "budgets": {}}
            for B in c25.BUDGETS:
                col = np.where(np.isnan(v1[:, B]), -1, v1[:, B])
                top = [PLANS[j] for j in np.argsort(-col)[:TOP]]
                rule = H.rule_plan(B)
                cand = sorted(set(top) | {rule})
                v2 = goal_values(cand, ev, RUNS2, 4102, g, nW)[:, B]
                best = cand[int(np.nanargmax(v2))]
                row["budgets"][B] = {"rule": [list(rule), float(v2[cand.index(rule)])],
                                     "best": [list(best), float(np.nanmax(v2))],
                                     "top": [[list(p), float(x)] for p, x in sorted(zip(cand, v2), key=lambda t: -t[1])]}
            out.append(row)
            print(f"{hn[:12]:<12} {tr:<10} {time.time() - t0:.0f}s", flush=True)
    json.dump(out, open(os.path.join(HERE, "c25b_results.json"), "w"), indent=1)
    print("\ncase | budget | rule's plan (with the coupon) | best plan found | gain (points)")
    for row in out:
        for B, c in row["budgets"].items():
            print(f"{row['horse'].split(' (')[0][:10]} {row['training']:<10} | {B} | {100 * c['rule'][1]:.1f}% | "
                  f"{100 * c['best'][1]:.1f}% {H.plan_name(tuple(c['best'][0]), B)} | {100 * (c['best'][1] - c['rule'][1]):+.1f}")


if __name__ == "__main__":
    main()
