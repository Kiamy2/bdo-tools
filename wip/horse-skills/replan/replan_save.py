"""C41 replan-save: re-planning during leveling to save coupons while keeping a chance target.

Goal at every decision (level 1, then levels 10/15/20/25 from the horse's real state): among the plans of the grid
(replan4.plans_from) and every coupon budget B from the plan's spending cap to what the horse still may use (a
total cap of COUPON_CAP for the horse), the (plan, B) with the fewest expected Change Coupons used, subject to the
horse's chance of the full set from now >= TARGET. If no (plan, B) reaches it: the best chance with every coupon
still allowed. 300 horses per plan (every budget at once), then the 10 cheapest (and those within 0.5 coupons, at
most 20) rerun with 2000 fresh horses; the cheapest of those that reaches the target (else the best chance) is
played. Budget B: the leveling spends at most the plan's cap, then the level-30 cleanup goes on until the set is
complete, it can't go on, or B coupons are used in total (from this decision on).
Each horse is played with the same random numbers in three ways:
  a  fixed: the level-1 plan and budget, kept to the end (hard stop at that budget);
  b  fixed plan, but the cleanup may use coupons up to COUPON_CAP in total;
  c  re-planned at each checkpoint (the new budget replaces the old one; total never above COUPON_CAP).
Score (exact, only the leveling is random): the chance of the full set after the cleanup and the expected
Change Coupons used in total (spent while leveling + the cleanup's expected use), both from the level-30 state.
Play rules: replan4.play (the tool's fast engine, reset included, no tickets).
Usage: python3 -I replan_save.py OUT.jsonl --horses N [--case t8p1]
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np                                                       # noqa: E402
import replan4 as R                                                      # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402

CASES = {"t8p1": {"horse": "T8 example (bdolytics icon horse_71)", "training": "Professional 1", "target": 0.85,
                  "coupon_cap": 40}}
COMMON = {"checkpoints": [10, 15, 20, 25], "point_bonus": 0.25, "runs1": 300, "runs2": 2000, "stage2_top": 10,
          "stage2_margin": 0.5, "stage2_max": 20, "first_runs": (1000, 4000), "seed": 20261121, "coupons": 0}


def score(S, have, pts, left):
    """Exact (chance of the full set, expected cleanup coupons used) from a level-30 state with 'left' coupons."""
    k = np.array([(have << F.PBITS) | pts], np.int64)
    z = np.zeros(1, np.int64)
    acc = F.cleanup_values(k, z, z, z, 1, left, 1, False, S.wa, S.n, np.int64(S.wmask), S.order_a, S.rare_a, S.pb,
                           used=True)
    return float(acc[0, left, 0]), float(acc[0, left, 2])


def choose(res, avail, target):
    """(plan, B, chance, expected used) per the goal, from Evaluator.plans results."""
    feas, best = [], None
    for p, r in res.items():
        for B in range(p[2] if p[0] != "at30" else 0, avail + 1):
            if r["full"][B] is not None and r["full"][B] >= target:
                feas.append((r["used"][B], -r["full"][B], p, B))
                break
        f = r["full"][avail]
        if best is None or (f, -r["used"][avail]) > (best[0], -best[1]):
            best = (f, r["used"][avail], p, avail)
    if feas:
        feas.sort()
        return [(u, -f, p, B) for u, f, p, B in feas]
    return None, best


def decide(S, s, level, have, avail, pts, seed, runs=None):
    runs = runs or (s["runs1"], s["runs2"])
    ev = F.Evaluator(S.horse, S.M, max_budget=avail, learned=S.names(have), start_level=level, points=pts,
                     point_bonus=s["point_bonus"])
    plans = R.plans_from(level, avail)
    r1 = ev.plans(plans, runs=runs[0], seed=seed * 2 + 1, used=True)
    c1 = choose(r1, avail, s["target"])
    if isinstance(c1, list):
        keep = [x[2] for x in c1[:s["stage2_top"]]]
        keep += [x[2] for x in c1 if x[0] <= c1[0][0] + s["stage2_margin"]][:s["stage2_max"]]
    else:
        ranked = sorted(r1, key=lambda p: -r1[p]["full"][avail])
        keep = ranked[:s["stage2_top"]]
    keep = sorted(set(keep))
    r2 = ev.plans(keep, runs=runs[1], seed=seed * 2 + 2, used=True)
    c2 = choose(r2, avail, s["target"])
    if isinstance(c2, list):
        u, f, p, B = c2[0]
    else:
        f, u, p, B = c2[1]
    return p, B, f, u


def play(S, s, plan, budget, horse_seed, replan_seed=None):
    """Returns the level-30 state (have, points, coupons spent, budget left) and the decisions made."""
    rnd = random.Random(horse_seed).random
    w, n, wmask = S.w, S.n, S.wmask
    full = (1 << n) - 1
    cap_total = s["coupon_cap"]
    have, pts, spent = 0, 0, 0
    st, sf, cap, T = plan
    used, latched, left = 0, False, budget
    decisions = []

    def swap(out):
        nonlocal have, pts, spent, used, left
        free = ~have & ~(1 << out) & full
        target = next((i for i in S.rare if free >> i & 1), -1)
        b = 1 + S.pb * pts
        ws = [(i, w[i] * b if i == target else w[i]) for i in range(n) if free >> i & 1]
        if not ws:
            return
        x = rnd() * sum(v for _, v in ws)
        new = ws[-1][0]
        for i, v in ws:
            x -= v
            if x < 0:
                new = i
                break
        have = (have & ~(1 << out)) | (1 << new)
        spent += 1
        used += 1
        left -= 1
        pts = 0 if new == target else pts + 1

    for lvl in range(1, 30):
        su = sum(w[i] for i in range(n) if not have >> i & 1)
        k = min(S.M / (su + S.horse.W), 1 / su) if su else 0
        x = rnd()
        for i in range(n):
            if not have >> i & 1:
                x -= k * w[i]
                if x < 0:
                    have |= 1 << i
                    break
        reached = lvl + 1
        if not (reached < sf or used >= cap or st == "at30"):
            if st == "coursier_switch" and bin(have).count("1") >= T:
                latched = True
            if st == "coursier" or (st == "coursier_switch" and not latched):
                for q in S.fod:
                    if have >> q & 1 and used < cap:
                        swap(q)
            elif S.cyc >= 0 and have >> S.cyc & 1 and used < cap:
                swap(S.cyc)
        if replan_seed is not None and reached in s["checkpoints"] and have & wmask != wmask:
            avail = cap_total - spent
            p, B, f, u = decide(S, s, reached, have, avail, pts, replan_seed * 100 + reached)
            decisions.append([reached, *p, B, round(f, 4), round(u, 2)])
            (st, sf, cap, T), left = p, B
            used, latched = 0, False
    return have, pts, spent, left, decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--horses", type=int, required=True)
    ap.add_argument("--case", default="t8p1", choices=list(CASES))
    a = ap.parse_args()
    s = dict(COMMON, **CASES[a.case])
    s["coupons"] = s["coupon_cap"]
    S = R.Setup(s)
    h = __import__("hashlib").sha256()
    for f in (__file__, R.__file__, F.__file__, R.H.__file__):
        h.update(open(f, "rb").read())
    ver = {"code_sha256": h.hexdigest()[:16]}
    done = 0
    if os.path.exists(a.out):
        lines = open(a.out).read().splitlines()
        head = json.loads(lines[0])
        if head["settings"] != json.loads(json.dumps(s)) or head["code_sha256"] != ver["code_sha256"]:
            sys.exit("settings or code differ from the file's header: refusing to append")
        done = len(lines) - 1
        plan, B0 = tuple(head["first_plan"]), head["first_budget"]
    else:
        t = time.time()
        plan, B0, f, u = decide(S, s, 1, 0, s["coupon_cap"], 0, s["seed"] * 1000 + 1, runs=s["first_runs"])
        with open(a.out, "w") as fh:
            fh.write(json.dumps({"settings": s, **ver, "first_plan": list(plan), "first_budget": B0,
                                 "first_chance": f, "first_used": u}) + "\n")
        print(f"level-1 choice: {plan}, budget {B0} -> {f:.1%}, {u:.2f} coupons expected ({time.time() - t:.0f}s)",
              flush=True)
    t0 = time.time()
    for i in range(done, a.horses):
        t = time.time()
        hs = s["seed"] * 1_000_003 + i
        have, pts, spent, left, _ = play(S, s, plan, B0, hs)
        fa, ua = score(S, have, pts, left)
        fb, ub = score(S, have, pts, s["coupon_cap"] - spent)
        have, pts, spent_c, left_c, dec = play(S, s, plan, B0, hs, replan_seed=s["seed"] % 100000 * 10_000 + i)
        fc, uc = score(S, have, pts, left_c)
        row = {"horse": i, "a": [round(fa, 6), round(spent + ua, 4)], "b": [round(fb, 6), round(spent + ub, 4)],
               "c": [round(fc, 6), round(spent_c + uc, 4)], "decisions": dec, "secs": round(time.time() - t, 1)}
        with open(a.out, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"horse {i + 1}/{a.horses} ({(time.time() - t0) / (i + 1 - done):.1f}s per horse)", flush=True)


if __name__ == "__main__":
    main()
