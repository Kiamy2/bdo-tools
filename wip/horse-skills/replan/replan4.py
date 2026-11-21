"""C32r: re-planning during leveling, with the Skill Change Points reset (C32 replan-v2 redone on the tool's engine).

Each horse is played twice with the same random numbers: with the level-1 plan kept to the end ("fixed"), and
re-planned at levels 10, 15, 20 and 25 from its real state (skills held, coupons left, points) ("replan").
Score: the exact chance of the full set after the level-30 cleanup (bdo.horses_fast.cleanup_values, reset
included), so only the leveling is random. The difference is paired per horse.
Plans and decisions as in replan3.py: All at 30, V0, V2 and 'V0 until T learned skills, then V2' (T 9-16), start
levels every 2 levels, caps on a grid; 300 horses per plan, then the top 10 (and those within 2 points, at most 20)
rerun with 2000 fresh horses; the best of those is played. Decisions are made after the level's level-up and
swaps; the new plan starts at the next level-up (its start level is at least the next level), and its spending
cap counts from that moment.
Play rules: those of the tool's fast engine (bdo/horses_fast._level30, no tickets): one pass per level; V0 swaps
Hind Kick then Fore Chop if held, V2 only Hind Kick; desired skill = the rarest missing wanted skill; points + 1
per coupon, 0 when it gives the desired skill.
Results: one JSON line per horse, resumable; header with settings and code hash (appends refused if they differ).
Usage: python3 -I replan4.py OUT.jsonl --horses N --case t8|doom|dine
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
sys.path[:0] = [REPO]

import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402

CASES = {
    "t8": {"horse": "T8 example (bdolytics icon horse_71)", "training": "Skilled 1", "coupons": 20},
    "doom": {"horse": "Doom (T9)", "training": "Beginner 1", "coupons": 20},
    "dine": {"horse": "Mythical Diné", "training": "Artisan 7", "coupons": 10},
}
COMMON = {"checkpoints": [10, 15, 20, 25], "point_bonus": 0.25, "runs1": 300, "runs2": 2000, "stage2_top": 10,
          "stage2_margin": 0.02, "stage2_max": 20, "first_runs": (1000, 4000), "seed": 20261121}
CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 20, 25, 30]
TS = list(range(9, 17))


class Setup:
    def __init__(self, s):
        d = H.load_data()
        self.horse = H.get_horse(d, s["horse"])
        self.M = self.horse.M(H.training_bonus(s["training"]), 0, 0)
        self.pool = list(self.horse.weights)
        ev = F.Evaluator(self.horse, self.M, max_budget=s["coupons"])
        w, n, W, M = ev.args
        lmask, wmask, fod, cyc, order, rare = ev.masks
        self.wa, self.order_a, self.rare_a = w, order, rare
        self.w, self.n, self.wmask = [float(x) for x in w], n, int(wmask)
        self.fod, self.cyc = [int(x) for x in fod], int(cyc)
        self.order, self.rare = [int(x) for x in order], [int(x) for x in rare]
        self.pb = s["point_bonus"]

    def names(self, mask):
        return [self.pool[i] for i in range(self.n) if mask >> i & 1]

    def score(self, have, pts, left):
        k = np.array([(have << F.PBITS) | pts], np.int64)
        acc = F.cleanup_values(k, np.zeros(1, np.int64), np.zeros(1, np.int64), np.zeros(1, np.int64), 1, left, 1,
                               False, self.wa, self.n, np.int64(self.wmask), self.order_a, self.rare_a, self.pb)
        return float(acc[0, left, 0])


def plans_from(level, left):
    starts = sorted(set([level + 1] + list(range(level + 1, 30, 2))))
    caps = sorted(set([c for c in CAPS if c <= left] + [left]))
    out = [("at30", 1, 0, 0)]
    for st in ("coursier", "coursier_v2"):
        out += [(st, sf, c, 0) for sf in starts for c in caps]
    out += [("coursier_switch", sf, c, T) for sf in starts for c in caps for T in TS]
    return out


def decide(S, s, level, have, left, pts, seed, runs=None):
    runs = runs or (s["runs1"], s["runs2"])
    ev = F.Evaluator(S.horse, S.M, max_budget=left, learned=S.names(have), start_level=level, points=pts,
                     point_bonus=s["point_bonus"])
    plans = plans_from(level, left)
    r1 = ev.plans(plans, runs=runs[0], seed=seed * 2 + 1)
    v1 = {p: r1[p]["full"][left] for p in plans}
    ranked = sorted(plans, key=lambda p: -v1[p])
    keep = set(ranked[:s["stage2_top"]])
    keep.update([p for p in ranked if v1[p] >= v1[ranked[0]] - s["stage2_margin"]][:s["stage2_max"]])
    keep = sorted(keep)
    r2 = ev.plans(keep, runs=runs[1], seed=seed * 2 + 2)
    best = max(keep, key=lambda p: r2[p]["full"][left])
    return best, r2[best]["full"][left]


def play(S, s, plan, horse_seed, replan_seed=None, decide_fn=None):
    rnd = random.Random(horse_seed).random
    w, n, wmask = S.w, S.n, S.wmask
    full = (1 << n) - 1
    have, left, pts = 0, s["coupons"], 0
    st, sf, cap, T = plan
    used, latched = 0, False
    decisions = []

    def swap(out):
        nonlocal have, left, pts, used
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
        left -= 1
        used += 1
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
        if decide_fn and reached in s["checkpoints"] and left > 0 and have & wmask != wmask:
            new_plan, chance = decide_fn(reached, have, left, pts, replan_seed * 100 + reached)
            decisions.append([reached] + list(new_plan) + [round(chance, 4)])
            st, sf, cap, T = new_plan
            used, latched = 0, False
    return {"chance": S.score(have, pts, left), "wanted_at30": bin(have & wmask).count("1"),
            "skills": bin(have).count("1"), "spent_leveling": s["coupons"] - left, "points": pts,
            "decisions": decisions}


def code_version():
    h = hashlib.sha256()
    for f in (__file__, os.path.join(REPO, "bdo", "horses_fast.py"), H.__file__,
              os.path.join(REPO, "data", "horse_skills.json")):
        h.update(open(f, "rb").read())
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                            text=True).stdout.strip()
    return {"code_sha256": h.hexdigest()[:16], "git_commit": commit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--horses", type=int, required=True)
    ap.add_argument("--case", default="t8", choices=list(CASES))
    a = ap.parse_args()
    s = dict(COMMON, **CASES[a.case])
    S = Setup(s)
    ver = code_version()
    done = 0
    if os.path.exists(a.out):
        lines = open(a.out).read().splitlines()
        head = json.loads(lines[0])
        if head["settings"] != json.loads(json.dumps(s)) or head["code_sha256"] != ver["code_sha256"]:
            sys.exit("settings or code differ from the file's header: refusing to append")
        done = len(lines) - 1
        plan = tuple(head["first_plan"])
    else:
        t = time.time()
        plan, chance = decide(S, s, 1, 0, s["coupons"], 0, s["seed"] * 1000 + 1, runs=s["first_runs"])
        with open(a.out, "w") as f:
            f.write(json.dumps({"settings": s, **ver, "first_plan": list(plan), "first_plan_chance": chance}) + "\n")
        print(f"level-1 plan: {plan} -> {chance:.1%} ({time.time() - t:.0f}s)", flush=True)
    t0 = time.time()
    for i in range(done, a.horses):
        t = time.time()
        hs = s["seed"] * 1_000_003 + i
        dec = lambda lv, hv, lf, pt, sd: decide(S, s, lv, hv, lf, pt, sd)
        fx = play(S, s, plan, hs)
        rp = play(S, s, plan, hs, replan_seed=s["seed"] % 100000 * 10_000 + i, decide_fn=dec)
        with open(a.out, "a") as f:
            f.write(json.dumps({"horse": i, "fixed": fx, "replan": rp, "secs": round(time.time() - t, 1)}) + "\n")
        if (i + 1) % 20 == 0:
            print(f"horse {i + 1}/{a.horses} ({(time.time() - t0) / (i + 1 - done):.2f}s per horse)", flush=True)


if __name__ == "__main__":
    main()
