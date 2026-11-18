"""C32 replan-v2, hard cases: re-planning during leveling with the V0 -> V2 switch strategy available.

Like replan2.py (paired horses, exact scoring of the level-30 cleanup, one JSON line per horse, resumable,
settings + code hash in the header), with:
- plans from All at 30, V0 (swap Hind Kick and Fore Chop), V2 (only Hind Kick), and
  'V0 until the horse holds T learned skills, then V2' (proto/c36_fast.py strategy 12);
- decisions on a coarser grid (start levels every 2 levels, about 12 spending caps, T 9-16), then the best ones
  rerun with more horses.
Play rules mirror c36_fast._level30x: no swap before the start level or once the spending cap is reached; for the
switch strategy, the skill count is checked from the start level on and the switch to V2 is final.

Usage: python3 -I replan3.py OUT.jsonl --horses N [--case t8|doom]
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
import c36_fast as X                                                     # noqa: E402
from cleanup_exact import Cleanup                                        # noqa: E402

CASES = {
    "t8": {"horse": "T8 example (bdolytics icon horse_71)", "training": "Skilled 1", "coupons": 20},
    "doom": {"horse": "Doom (T9)", "training": "Beginner 1", "coupons": 20},
}
COMMON = {"checkpoints": [10, 15, 20, 25], "point_bonus": 0.25, "runs1": 300, "runs2": 2000, "stage2_top": 10,
          "stage2_margin": 0.02, "stage2_max": 20, "first_runs": (1000, 4000), "seed": 20261118}
CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 20, 25, 30]
TS = list(range(9, 17))


class Setup:
    def __init__(self, s):
        d = H.load_data()
        self.horse = H.get_horse(d, s["horse"])
        self.M = self.horse.M(H.training_bonus(s["training"]), 0, 0)
        self.pool = list(self.horse.weights)
        ev = X.Evaluator(self.horse, self.M, C=s["coupons"])
        self.table = ev.table                                       # shared exact cleanup table (G only)
        w, n, W, M, lmask, wmask, fod, cyc, rare = ev.a
        self.w, self.n, self.wmask = [float(x) for x in w], n, int(wmask)
        self.fod, self.cyc = [int(x) for x in fod], int(cyc)
        self.rare = [int(x) for x in rare]
        order = sorted(range(n), key=lambda i: (self.w[i], i))
        self.CL = Cleanup(self.w, self.wmask, order, self.rare, s["point_bonus"])

    def names(self, mask):
        return [self.pool[i] for i in range(self.n) if mask >> i & 1]

    def score(self, have, pts, left):
        k = np.array([(have << X.PBITS) | pts], np.int64)
        self.table.ensure(k)
        return float(self.table.G[X._rows(k, self.table.d)[0], left])


def plans_from(level, left):
    starts = sorted(set([level + 1] + list(range(level + 1, 30, 2))))
    caps = sorted(set([c for c in CAPS if c <= left] + [left]))
    out = [(0, level + 1, 0, 0, 0)]
    for st in (1, 6):
        out += [(st, s, c, 0, 0) for s in starts for c in caps]
    out += [(12, s, c, 0, T) for s in starts for c in caps for T in TS]
    return out


def decide(S, s, level, have, left, pts, seed, runs=None):
    runs = runs or (s["runs1"], s["runs2"])
    ev = X.Evaluator(S.horse, S.M, C=left, table=S.table, learned=S.names(have), start_level=level, points=pts)
    plans = plans_from(level, left)
    v1 = {p: ev.plan(*p, runs=runs[0], seed=seed * 2 + 1)[left] for p in plans}
    ranked = sorted(plans, key=lambda p: -v1[p])
    keep = set(ranked[:s["stage2_top"]])
    keep.update([p for p in ranked if v1[p] >= v1[ranked[0]] - s["stage2_margin"]][:s["stage2_max"]])
    v2 = {p: ev.plan(*p, runs=runs[1], seed=seed * 2 + 2)[left] for p in keep}
    best = max(sorted(keep), key=lambda p: v2[p])
    return best, v2[best]


def play(S, s, plan, horse_seed, replan_seed=None, decide_fn=None):
    rnd = random.Random(horse_seed).random
    w, n, wmask = S.w, S.n, S.wmask
    have, left, pts = 0, s["coupons"], 0
    st, sf, cap, xa, T = plan
    used, latched = 0, False
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
        have = new_set
        left -= 1
        pts += 1
        used += 1
        return 0

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
        if not (reached < sf or used >= cap or st == 0):
            if st == 12 and bin(have).count("1") >= T:
                latched = True
            v0 = st == 1 or (st == 12 and not latched)
            if v0:
                for q in S.fod:
                    if have >> q & 1 and used < cap:
                        swap(q)
            elif S.cyc >= 0 and have >> S.cyc & 1 and used < cap:
                swap(S.cyc)
        if decide_fn and reached in s["checkpoints"] and left > 0 and have & wmask != wmask:
            new_plan, chance = decide_fn(reached, have, left, pts, replan_seed * 100 + reached)
            decisions.append([reached] + list(map(int, new_plan)) + [round(chance, 4)])
            st, sf, cap, xa, T = new_plan
            used, latched = 0, False
    return {"chance": S.score(have, pts, left), "wanted_at30": bin(have & wmask).count("1"),
            "skills": bin(have).count("1"), "spent_leveling": s["coupons"] - left, "decisions": decisions}


def code_version():
    h = hashlib.sha256()
    for f in (__file__, X.__file__, os.path.join(PROTO, "cleanup_exact.py"), os.path.join(REPO, "bdo", "horses_fast.py"),
              H.__file__, os.path.join(REPO, "data", "horse_skills.json")):
        h.update(open(f, "rb").read())
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
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
            f.write(json.dumps({"settings": s, **ver, "first_plan": list(map(int, plan)),
                                "first_plan_chance": chance}) + "\n")
        print(f"level-1 plan: {plan} -> {chance:.1%} ({time.time() - t:.0f}s)", flush=True)
    for i in range(done, a.horses):
        t = time.time()
        hs = s["seed"] * 1_000_003 + i
        dec = lambda lv, hv, lf, pt, sd: decide(S, s, lv, hv, lf, pt, sd)
        fx = play(S, s, plan, hs)
        rp = play(S, s, plan, hs, replan_seed=s["seed"] % 100000 * 10_000 + i, decide_fn=dec)
        with open(a.out, "a") as f:
            f.write(json.dumps({"horse": i, "fixed": fx, "replan": rp, "secs": round(time.time() - t, 1)}) + "\n")
        if (i + 1) % 20 == 0:
            print(f"horse {i + 1}/{a.horses} ({time.time() - t:.1f}s for the last one)", flush=True)


if __name__ == "__main__":
    main()
