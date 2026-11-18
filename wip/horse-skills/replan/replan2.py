"""C32 replan-v2: does re-planning during leveling beat the best fixed plan, now that V2 exists?

Like replan.py, with three changes:
- plans can be All at 30, plain Coursier or V2 (cycle Hind Kick, keep Fore Chop);
- decisions are evaluated with the exact level-30 cleanup (proto/table_nb.py);
- each played horse is scored at level 30 by its exact chance of finishing the cleanup with its coupons left
  (instead of playing the cleanup out): same average, much less noise.
Each horse is played twice with the same random numbers (fixed plan / re-planned). One JSON line per horse;
resumes after the last saved horse; refuses to append if settings or code differ.

Usage: python3 -I replan2.py OUT.jsonl --horses N
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
PROTO = os.path.join(HERE, "..", "proto")
sys.path[:0] = [REPO, PROTO]

import numpy as np                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
import table_nb as T                                                     # noqa: E402
from cleanup_exact import Cleanup                                        # noqa: E402

SETTINGS = {"horse": "Mythical Diné", "training_bonus": 21.7, "gear": 0, "brand": 0, "coupons": 10,
            "checkpoints": [10, 15, 20, 25], "point_bonus": 0.25, "families": ["at30", "coursier", "coursier_v2"],
            "runs1": 500, "runs2": 2000, "stage2_top": 8, "stage2_margin": 0.02, "stage2_max": 20,
            "seed": 20261118}
CODE = {"at30": 0, "coursier": 1, "coursier_v2": 6}


class Setup:
    def __init__(self, s):
        d = H.load_data()
        self.horse = H.get_horse(d, s["horse"])
        self.M = self.horse.M(s["training_bonus"], s["gear"], s["brand"])
        ev = T.Evaluator(self.horse, self.M, max_budget=s["coupons"])
        A = ev.args
        self.pool = list(self.horse.weights)
        self.w = [float(x) for x in A["w"]]
        self.n = A["n"]
        self.wmask = int(A["wmask"])
        self.fod = [int(x) for x in A["fod"]]
        self.order = [int(x) for x in A["order"]]
        self.rare = ev.rare
        self.CL = Cleanup(self.w, self.wmask, self.order, self.rare, s["point_bonus"])
        # one shared exact table: points never exceed the coupon budget
        self.table = T.Table(self.w, self.wmask, self.order, self.rare, C=s["coupons"], pmax=s["coupons"],
                             point_bonus=s["point_bonus"])

    def names(self, mask):
        return [self.pool[i] for i in range(self.n) if mask >> i & 1]

    def score(self, have, pts, left):
        """exact chance of ending with every wanted skill, from held skills at 30 with 'left' coupons"""
        self.table.ensure([(have << T.PBITS) | pts])
        r = self.table.rows_of([(have << T.PBITS) | pts])[0]
        return float(self.table.G[r, min(left, self.table.C)])


def decide(S, s, level, have, left, pts, seed):
    """Best plan from this state for the chance of the full set with the coupons left."""
    ev = T.Evaluator(S.horse, S.M, table=S.table, max_budget=left, learned=S.names(have), points=pts,
                     start_level=level, point_bonus=s["point_bonus"])
    plans = [("at30", level + 1, 0)] + [(f, sf, cap) for f in s["families"] if f != "at30"
                                        for sf in range(level + 1, 31) for cap in range(1, left + 1)]
    v1 = {p: ev.plan(*p, runs=s["runs1"], seed=seed * 2 + 1)["full"][left] for p in plans}
    ranked = sorted(plans, key=lambda p: -v1[p])
    keep = list(ranked[:s["stage2_top"]])
    keep += [p for p in ranked if v1[p] >= v1[ranked[0]] - s["stage2_margin"]][:s["stage2_max"]]
    keep = sorted(set(keep))
    v2 = {p: ev.plan(*p, runs=s["runs2"], seed=seed * 2 + 2)["full"][left] for p in keep}
    best = max(keep, key=lambda p: v2[p])
    return best, v2[best]


def play(S, s, plan, horse_seed, replan_seed=None, decide_fn=None):
    """Plays one horse from level 1 to 30 (same rules as table_nb._level30 for at30 / coursier / V2), re-planning at
    the checkpoints if decide_fn is set; returns the exact chance of finishing the cleanup, plus details."""
    rnd = random.Random(horse_seed).random
    w, n, wmask, fod = S.w, S.n, S.wmask, S.fod
    have, left, pts = 0, s["coupons"], 0
    st, sf, cap = plan
    used = 0
    decisions = []

    def swap(out):
        nonlocal have, left, pts, used
        tr = S.CL.transitions(have, pts, out)
        if not tr:
            return -1
        x = rnd()
        new_set = tr[-1][0]
        for cand, pr in tr:
            x -= pr
            if x < 0:
                new_set = cand
                break
        new = (new_set & ~have).bit_length() - 1
        have = new_set
        left -= 1
        pts += 1
        used += 1
        return new

    for lvl in range(1, 30):
        su = sum(w[i] for i in range(n) if not have >> i & 1)
        k = min(S.M / (su + S.horse.W), 1 / su) if su else 0
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
            if st == "coursier":
                for q in fod:
                    if have >> q & 1 and used < cap:
                        swap(q)
            elif st == "coursier_v2":
                if fod and have >> fod[0] & 1 and used < cap:
                    swap(fod[0])
        if decide_fn and reached in s["checkpoints"] and left > 0 and have & wmask != wmask:
            new_plan, chance = decide_fn(reached, have, left, pts, replan_seed * 100 + reached)
            decisions.append([reached, new_plan[0], new_plan[1], new_plan[2], round(chance, 4)])
            st, sf, cap = new_plan
            used = 0
    return {"chance": S.score(have, pts, left), "wanted_at30": bin(have & wmask).count("1"),
            "skills": bin(have).count("1"), "spent_leveling": s["coupons"] - left, "decisions": decisions}


def code_version():
    h = hashlib.sha256()
    for f in (__file__, T.__file__, os.path.join(PROTO, "sim_fast.py"), os.path.join(PROTO, "cleanup_exact.py"),
              H.__file__, os.path.join(REPO, "data", "horse_skills.json")):
        h.update(open(f, "rb").read())
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                            text=True).stdout.strip()
    return {"code_sha256": h.hexdigest()[:16], "git_commit": commit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--horses", type=int, required=True)
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
        plan = tuple(head["first_plan"])
    else:
        t = time.time()
        plan, chance = decide(S, SETTINGS, 1, 0, SETTINGS["coupons"], 0, SETTINGS["seed"] * 1000 + 1)
        with open(a.out, "w") as f:
            f.write(json.dumps({"settings": SETTINGS, **ver, "first_plan": list(plan),
                                "first_plan_chance": chance}) + "\n")
        print(f"level-1 plan: {plan} -> {chance:.1%} ({time.time() - t:.0f}s)", flush=True)
    for i in range(done, a.horses):
        t = time.time()
        hs = SETTINGS["seed"] * 1_000_003 + i
        dec = lambda lv, hv, lf, pt, sd: decide(S, SETTINGS, lv, hv, lf, pt, sd)
        fx = play(S, SETTINGS, plan, hs)
        rp = play(S, SETTINGS, plan, hs, replan_seed=SETTINGS["seed"] % 100000 * 10_000 + i, decide_fn=dec)
        with open(a.out, "a") as f:
            f.write(json.dumps({"horse": i, "fixed": fx, "replan": rp, "secs": round(time.time() - t, 1)}) + "\n")
        if (i + 1) % 20 == 0:
            print(f"horse {i + 1}/{a.horses} ({time.time() - t:.1f}s for the last one)", flush=True)


if __name__ == "__main__":
    main()
