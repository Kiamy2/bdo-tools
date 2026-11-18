"""Experiment: does re-planning during leveling beat the best fixed plan?

Each simulated horse is played twice with the same random numbers:
- fixed: the best plan chosen at level 1, followed to the end;
- re-planned: same start, but at the checkpoint levels the plan is chosen again from the horse's real state
  (learned skills, coupons left, Skill Change Points).

A decision tries every plan from the current state: at30, and coursier / once / hard with every start level from
the next level to 30 and every spending cap up to the coupons left. Stage 1 runs each with RUNS1 simulated horses,
stage 2 reruns the best ones with RUNS2 fresh horses and keeps the best. Decisions use their own random numbers
(seeded by experiment seed, horse number, checkpoint), never the played horse's.

Results: one JSON line per horse in the output file, after a header line with the settings. Running again
resumes after the last saved horse; --horses N extends the file to N horses. Settings must match the header.

Usage: python3 -I replan.py OUT.jsonl --horses 300
"""
import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path[:0] = [REPO, os.path.join(HERE, "..", "proto")]

import numpy as np                                                       # noqa: E402
import numba                                                             # noqa: E402
from bdo import horses as H                                              # noqa: E402
import sim_fast as F                                                     # noqa: E402

SETTINGS = {
    "horse": "Mythical Diné", "training_bonus": 21.7, "gear": 0, "brand": 0,
    "coupons": 15, "checkpoints": [10, 15, 20, 25], "point_bonus": 0.25,
    "runs1": 1000, "runs2": 4000, "stage2_top": 6, "stage2_margin": 0.03, "stage2_max": 15,
    "seed": 20261118,
}
CODES = {"at30": 0, "coursier": 1, "once": 2, "hard": 3}
NAMES = {v: k for k, v in CODES.items()}


@numba.njit(cache=True, parallel=True)
def eval_plans(strat, swap_from, cap, runs, seed, w, n, W, M, budget, start_level, lmask, wmask, fod, order, rare,
               point_bonus, points, max_level):
    """For each plan: number of simulated horses (out of runs) ending with every wanted skill within budget,
    and the sum of wanted skills at the end. Same random numbers for every plan (common random numbers)."""
    P = strat.shape[0]
    succ = np.zeros(P, np.int64)
    wsum = np.zeros(P, np.int64)
    for p in numba.prange(P):
        traj = np.empty(budget + 1, np.int64)
        s_ = 0
        ws_ = 0
        for r in range(runs):
            spent, need, sk = F._one_horse(r, seed, w, n, W, M, strat[p], swap_from[p], cap[p], budget, 0,
                                           start_level, lmask, wmask, fod, order, rare, point_bonus, points,
                                           max_level, traj)
            if need >= 0 and need <= budget:
                s_ += 1
            j = budget - spent
            if j > budget:
                j = budget
            ws_ += traj[j]
        succ[p] = s_
        wsum[p] = ws_
    return succ, wsum


class Setup:
    def __init__(self, s):
        d = H.load_data()
        self.horse = H.get_horse(d, s["horse"])
        self.M = self.horse.M(s["training_bonus"], s["gear"], s["brand"])
        pool, w, wmask, lmask, fod, order, nw = F._prepare(self.horse, "coursier", (), None, None)
        self.pool, self.w, self.wmask, self.fod, self.order, self.n_wanted = pool, w, wmask, fod, order, nw
        self.n = len(pool)
        self.rare = [i for i in order if wmask >> i & 1]
        self.W = float(self.horse.W)
        self.np = dict(w=np.array(w), fod=np.array(fod, np.int64), order=np.array(order, np.int64),
                       rare=np.array(self.rare, np.int64))


def decide(S, s, level, have, coupons_left, pts, seed):
    """Best plan (strategy, swap_from, cap) from this state for the chance of the full set with the coupons left."""
    plans = [(0, level + 1, 0)]
    for st in (1, 2, 3):
        for sf in range(level + 1, 31):
            for cap in range(1, coupons_left + 1):
                plans.append((st, sf, cap))
    arr = np.array(plans, np.int64)

    def run(idx, runs, sd):
        sub = arr[idx]
        succ, wsum = eval_plans(sub[:, 0].copy(), sub[:, 1].copy(), sub[:, 2].copy(), runs, sd, S.np["w"], S.n,
                                S.W, float(S.M), coupons_left, level, np.int64(have), np.int64(S.wmask),
                                S.np["fod"], S.np["order"], S.np["rare"], s["point_bonus"], pts, 30)
        return succ / runs, wsum / runs

    p1, _ = run(np.arange(len(plans)), s["runs1"], seed * 2 + 1)
    ranked = np.argsort(-p1, kind="stable")
    keep = list(ranked[:s["stage2_top"]])
    close = [i for i in ranked if p1[i] >= p1[ranked[0]] - s["stage2_margin"]][:s["stage2_max"]]
    keep = sorted(set(keep) | set(close))
    p2, w2 = run(np.array(keep), s["runs2"], seed * 2 + 2)
    b = int(np.argmax(p2))
    st, sf, cap = plans[keep[b]]
    return (int(st), int(sf), int(cap)), float(p2[b])


def play(S, s, plan, horse_seed, replan_seed=None, decide_fn=None, log=None):
    """Plays one horse from level 1 to 30 with the given plan; if decide_fn is set, re-plans at the checkpoints.
    Mirrors sim_fast._one_horse / bdo.horses.simulate_plan rule for rule. Returns a result dict."""
    rnd = random.Random(horse_seed).random
    w, n, wmask, order, fod, rare = S.w, S.n, S.wmask, S.order, S.fod, S.rare
    full = (1 << n) - 1
    have, left, pts = 0, s["coupons"], 0
    st, sf, cap = plan
    used = 0                                      # coupons used by the current plan while leveling
    pb = s["point_bonus"]
    decisions = []

    def swap(out):
        nonlocal have, left, pts, used
        free = ~have & ~(1 << out) & full
        target = next((i for i in rare if free >> i & 1), -1)
        boost = 1 + pb * pts
        tot = sum(w[i] * boost if i == target else w[i] for i in range(n) if free >> i & 1)
        if tot == 0:
            return -1
        x = rnd() * tot
        new = -1
        for i in range(n):
            if free >> i & 1:
                new = i
                x -= w[i] * boost if i == target else w[i]
                if x < 0:
                    break
        have = (have & ~(1 << out)) | (1 << new)
        left -= 1
        pts += 1
        used += 1
        return new

    for lvl in range(1, 30):
        su = sum(w[i] for i in range(n) if not have >> i & 1)
        k = min(S.M / (su + S.W), 1 / su) if su else 0
        x, got = rnd(), -1
        for i in range(n):
            if not have >> i & 1:
                x -= k * w[i]
                if x < 0:
                    got = i
                    break
        if got >= 0:
            have |= 1 << got
        reached = lvl + 1
        if not (reached < sf or used >= cap):
            if st == 1:
                for q in fod:
                    if have >> q & 1 and used < cap:
                        swap(q)
            elif st == 2:
                if reached == sf and sf > 1:
                    todo = [i for i in order if have >> i & 1 and not wmask >> i & 1]
                else:
                    todo = [got]
                for q in todo:
                    if q >= 0 and not wmask >> q & 1 and have >> q & 1 and used < cap:
                        swap(q)
            elif st == 3:
                for q in [i for i in order if have >> i & 1 and not wmask >> i & 1]:
                    slot = q
                    while slot >= 0 and not wmask >> slot & 1 and have >> slot & 1 and used < cap:
                        slot = swap(slot)
        if decide_fn and reached in s["checkpoints"] and left > 0 and have & wmask != wmask:
            new_plan, chance = decide_fn(reached, have, left, pts, replan_seed * 100 + reached)
            decisions.append([reached, NAMES[new_plan[0]], new_plan[1], new_plan[2], round(chance, 4)])
            st, sf, cap = new_plan
            used = 0
    leveling_spent = s["coupons"] - left
    for q in [i for i in order if have >> i & 1 and not wmask >> i & 1]:
        slot = q
        while slot >= 0 and not wmask >> slot & 1 and have & wmask != wmask and left > 0:
            slot = swap(slot)
        if have & wmask == wmask or left == 0:
            break
    return {"full": int(have & wmask == wmask), "wanted": bin(have & wmask).count("1"),
            "skills": bin(have).count("1"), "spent": s["coupons"] - left, "spent_leveling": leveling_spent,
            "decisions": decisions}


def code_version():
    h = hashlib.sha256()
    for f in (__file__, F.__file__, H.__file__):
        h.update(open(f, "rb").read())
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                                text=True).stdout.strip()
    except OSError:
        commit = "?"
    return {"code_sha256": h.hexdigest()[:16], "git_commit": commit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--horses", type=int, required=True, help="total number of horses the file should hold")
    a = ap.parse_args()
    S = Setup(SETTINGS)
    ver = code_version()
    done = 0
    if os.path.exists(a.out):
        lines = open(a.out).read().splitlines()
        head = json.loads(lines[0])
        if head["settings"] != SETTINGS or head["code_sha256"] != ver["code_sha256"]:
            sys.exit("settings or code differ from the file's header: refusing to append")
        done = len(lines) - 1
        first = head["first_plan"]
    else:
        t = time.time()
        plan, chance = decide(S, SETTINGS, 1, 0, SETTINGS["coupons"], 0, SETTINGS["seed"] * 1000 + 1)
        first = {"plan": [plan[0], plan[1], plan[2]], "chance": chance}
        with open(a.out, "w") as f:
            f.write(json.dumps({"settings": SETTINGS, **ver, "first_plan": first,
                                "first_plan_name": [NAMES[plan[0]], plan[1], plan[2]]}) + "\n")
        print(f"level-1 plan: {NAMES[plan[0]]} from {plan[1]}, spend <= {plan[2]}: {chance:.1%} "
              f"({time.time() - t:.0f}s)", flush=True)
    plan = tuple(first["plan"])
    for i in range(done, a.horses):
        t = time.time()
        hs = SETTINGS["seed"] * 1_000_003 + i
        dec = lambda lv, hv, lf, pt, sd: decide(S, SETTINGS, lv, hv, lf, pt, sd)
        fx = play(S, SETTINGS, plan, hs)
        rp = play(S, SETTINGS, plan, hs, replan_seed=SETTINGS["seed"] % 100000 * 10_000 + i, decide_fn=dec)
        with open(a.out, "a") as f:
            f.write(json.dumps({"horse": i, "fixed": fx, "replan": rp, "secs": round(time.time() - t, 1)}) + "\n")
        if (i + 1) % 10 == 0:
            print(f"horse {i + 1}/{a.horses} ({time.time() - t:.1f}s for the last one)", flush=True)


if __name__ == "__main__":
    main()
