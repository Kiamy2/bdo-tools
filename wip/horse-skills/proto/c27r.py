"""C27r: C27 (best possible level-30 cleanup) redone with the Skill Change Points reset (points back to 0 when the
coupon gives the desired skill).

The swapped skill is the rule's (the rarest unwanted skill held); the desired skill is chosen. Variants, each
computed exactly (its own best choice at every step, per goal):
  R: the rule (desired = the rarest missing wanted skill);
  W: any missing wanted skill as desired;
  A: any skill that can be drawn as desired, unwanted ones included (a rare unwanted desired skill keeps the
     points: a wanted skill drawn then isn't the desired one). Assumes the game lets you pick any such skill.
Goals: G = chance of the full set, H = expected wanted skills; each goal has its own best choices.
Leveling: the tool's fast engine (reset included), rule plans for 10/15/20 coupons and at30, 4000 horses each.
DP: layers by coupons left (c = 0..C) over every state reachable from the end-of-leveling states (needed: with
variant A a hit on an unwanted desired skill keeps the wanted count and resets the points, so the (wanted, points)
order of the tool's sweep doesn't hold).
Checks: R equals the tool's exact cleanup (Evaluator.plans) for the same horses.
Usage: python3 -I c27r.py [quick]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE)))]
import numpy as np                                                       # noqa: E402
import numba as nb                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402
from bdo.horses_fast import _pop, _slot, PBITS, PMASK                    # noqa: E402

NV = 6                                                                   # GR HR GW HW GA HA


@nb.njit(cache=True, parallel=True)
def _succ(keys, n, wmask, order):
    nW = _pop(wmask)
    full = (np.int64(1) << n) - 1
    out = np.full(len(keys) * 2 * n, -1, np.int64)
    for j in nb.prange(len(keys)):
        S = keys[j] >> PBITS
        p = keys[j] & PMASK
        if _pop(S & wmask) == nW:
            continue
        o = _slot(S, wmask, order)
        if o < 0:
            continue
        free = ~S & ~(np.int64(1) << o) & full
        m = j * 2 * n
        for i in range(n):
            if (free >> i) & 1:
                S2 = (S & ~(np.int64(1) << o)) | (np.int64(1) << i)
                out[m] = (S2 << PBITS) | (p + 1)
                out[m + 1] = S2 << PBITS
                m += 2
    return out


def reach(hk, C, n, wmask, order):
    seen = np.unique(hk)
    cur = seen
    for _ in range(C):
        nxt = np.unique(_succ(cur, n, wmask, order))
        nxt = nxt[nxt >= 0]
        cur = np.setdiff1d(nxt, seen, assume_unique=True)
        if not len(cur):
            break
        seen = np.union1d(seen, cur)
    return seen


@nb.njit(cache=True, parallel=True)
def _layer(K, prev, cur, c, w, n, wmask, order, rare, pb):
    nW = _pop(wmask)
    full = (np.int64(1) << n) - 1
    for r in nb.prange(len(K)):
        S = K[r] >> PBITS
        p = K[r] & PMASK
        hw = _pop(S & wmask)
        o = _slot(S, wmask, order) if hw < nW else -1
        if c == 0 or o < 0:
            for v in range(3):
                cur[r, 2 * v] = 1.0 if hw == nW else 0.0
                cur[r, 2 * v + 1] = hw
            continue
        free = ~S & ~(np.int64(1) << o) & full
        b = 1.0 + pb * p
        idx1 = np.empty(n, np.int64)
        idx0 = np.empty(n, np.int64)
        Wf = 0.0
        for i in range(n):
            if (free >> i) & 1:
                S2 = (S & ~(np.int64(1) << o)) | (np.int64(1) << i)
                idx1[i] = np.searchsorted(K, (S2 << PBITS) | (p + 1))
                idx0[i] = np.searchsorted(K, S2 << PBITS)
                Wf += w[i]
        rt = -1
        for i in rare:
            if (free >> i) & 1:
                rt = i
                break
        for col in range(NV):
            v = col // 2
            A = 0.0
            for i in range(n):
                if (free >> i) & 1:
                    A += w[i] * prev[idx1[i], col]
            best = -1.0
            for t in range(n):
                if not (free >> t) & 1:
                    continue
                if v == 0 and t != rt:
                    continue
                if v == 1 and not (wmask >> t) & 1:
                    continue
                val = (A - w[t] * prev[idx1[t], col] + w[t] * b * prev[idx0[t], col]) / (Wf + w[t] * (b - 1.0))
                if val > best:
                    best = val
            cur[r, col] = best


def run_case(name, training, C=20, runs=4000, seed=27, budgets=(10, 15, 20)):
    h = H.get_horse(H.load_data(), name)
    M = h.M(H.training_bonus(training), 0, 0)
    ev = F.Evaluator(h, M, max_budget=C)
    w, n, W, Mx = ev.args
    lmask, wmask, fod, cyc, order, rare = ev.masks
    plans = [("at30", 1, 0, 0)] + [H.rule_plan(B) for B in budgets]
    hk, hb, hp = [], [], []
    for j, (st, lv, cap, T) in enumerate(plans):
        S, base, pts = F._many30(runs, seed, w, n, W, Mx, F.CODES[st], lv, cap if st != "at30" else 0, 0, 1, lmask,
                                 wmask, fod, cyc, order, rare, 0.25, 0, 30, T, False)
        hk.append((S << PBITS) | pts)
        hb.append(base)
        hp.append(np.full(runs, j))
    hk, hb, hp = map(np.concatenate, (hk, hb, hp))
    t0 = time.time()
    K = reach(hk, C, n, wmask, order)
    t1 = time.time() - t0
    rows = np.searchsorted(K, hk)
    prev = np.zeros((len(K), NV))
    cur = np.zeros((len(K), NV))
    acc = np.zeros((len(plans), C + 1, NV))
    for c in range(C + 1):
        _layer(K, prev, cur, c, w, n, wmask, order, rare, 0.25)
        B = hb + c
        ok = B <= C
        np.add.at(acc, (hp[ok], B[ok]), cur[rows[ok]])
        prev, cur = cur, prev
    t2 = time.time() - t0 - t1
    ref = ev.plans(plans, runs=runs, seed=seed)
    out = []
    for j, p in enumerate(plans):
        for Bq in (budgets if p[0] == "at30" else [b for b in budgets if H.rule_plan(b) == p][:1]):
            v = acc[j, Bq] / runs
            dref = abs(v[0] - ref[p]["full"][Bq]) + abs(v[1] - ref[p]["wanted"][Bq])
            out.append((p, Bq, v, dref))
    return out, len(K), t1, t2


if __name__ == "__main__":
    cases = [("Mythical Diné", "Artisan 7"), ("Doom (T9)", "Artisan 7"), ("T8 example (bdolytics icon horse_71)", "Professional 10"),
             ("T8 example (bdolytics icon horse_71)", "Skilled 1"), ("Doom (T9)", "Beginner 1")]
    if sys.argv[1:] == ["quick"]:
        cases = cases[:1]
    print("full set (G) and expected wanted skills (H) after the cleanup: R = rule, W = best wanted desired, "
          "A = best any desired; gains vs R")
    for name, tr in cases:
        res, ns, t1, t2 = run_case(name, tr)
        print(f"== {name} | {tr} | {ns} states, reach {t1:.0f}s, DP {t2:.0f}s")
        for p, B, v, dref in res:
            print(f"  {H.plan_name(p, B)[:62]:62s} {B:2d} coupons: G R {100 * v[0]:6.2f}% W {100 * (v[2] - v[0]):+.3f} "
                  f"A {100 * (v[4] - v[0]):+.3f} | H R {v[1]:.3f} W {v[3] - v[1]:+.3f} A {v[5] - v[1]:+.3f} "
                  f"| R vs tool {dref:.1e}", flush=True)
