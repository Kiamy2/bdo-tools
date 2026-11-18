import sys, os, time, random, math
sys.path[:0] = ["/home/claude/bdo-tools", os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "replan")]
import numpy as np
import replan as R
from cleanup_exact import Cleanup

S0 = R.Setup(R.SETTINGS); s = dict(R.SETTINGS)
CL = Cleanup(S0.w, S0.wmask, S0.order, S0.rare)
C = 40

def level_only(plan, seed, coupons=40):
    """play() without the cleanup: returns (S at 30, coupons spent while leveling = points)"""
    s2 = dict(s); s2["coupons"] = coupons
    st = dict(state=None)
    # reuse play() but stop before cleanup by giving it 0 coupons left at 30: run with a wrapper copy
    rnd = random.Random(seed).random
    w, n, wmask, order, fod = S0.w, S0.n, S0.wmask, S0.order, S0.fod
    have, pts, used = 0, 0, 0
    stc, sf, cap = plan
    def swap(out):
        nonlocal have, pts, used
        S2 = None
        trans = CL.transitions(have, pts, out)
        x = rnd()
        for cand, pr in trans:
            x -= pr
            if x < 0:
                S2 = cand; break
        if not trans: return -1          # every other skill already learned: nothing to swap to
        if S2 is None: S2 = trans[-1][0]
        new = (S2 & ~have).bit_length() - 1
        have = S2; pts += 1; used += 1
        return new
    for lvl in range(1, 30):
        su = sum(w[i] for i in range(n) if not have >> i & 1)
        k = min(S0.M / (su + S0.W), 1 / su) if su else 0
        x, got = rnd(), -1
        for i in range(n):
            if not have >> i & 1:
                x -= k * w[i]
                if x < 0: got = i; break
        if got >= 0: have |= 1 << got
        reached = lvl + 1
        if reached < sf or used >= cap: continue
        if stc == 1:
            for q in fod:
                if have >> q & 1 and used < cap: swap(q)
    return have, used

for plan in [(1, 20, 5), (0, 2, 0)]:
    print(f"== plan {R.NAMES[plan[0]]} from {plan[1]}, spend <= {plan[2]}")
    N = 4000
    states = [level_only(plan, 7_000_000 + i) for i in range(N)]
    # (a) rules compared by Monte Carlo
    for rule in ("slot", "rarest"):
        rng = random.Random(11)
        T = []
        for S, base in states:
            t = CL.mc_needed(S, base, rng, rule)
            T.append(math.inf if t is None else base + t)
        print(f"  MC rule {rule:6}: full set with 10/15/20/30 coupons: " + " ".join(f"{100*sum(t <= b for t in T)/N:5.1f}%" for b in (10, 15, 20, 30)))
    # (b) exact table for 'rarest'
    t0 = time.time()
    starts = list({(S, base) for S, base in states})
    G = CL.table(starts, C)
    exact = {b: sum(G[(S, base)][b - base] if b >= base else 0 for S, base in states) / N for b in (10, 15, 20, 30)}
    print(f"  exact 'rarest' (same {N} level-30 states): " + " ".join(f"{100*exact[b]:5.1f}%" for b in (10, 15, 20, 30)) +
          f"   [{len(starts)} start states, {len(G)} table entries, {time.time()-t0:.1f}s]")
