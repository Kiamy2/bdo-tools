"""C25c: with a Selection Coupon planned for the end, should the swaps while leveling also keep the rarest missing
skill for it (desired skill = the next rarest missing wanted skill), like the adapted cleanup (c25 'end2')?

Leveling: a copy of bdo/horses_fast._level30 (strategies at30, coursier, coursier_v2, coursier_switch; no tickets)
with keep_rarest for the swaps' desired skill; with keep_rarest=False it reproduces the tool horse for horse.
Goal and method as c25b (full set with the coupon at the end, end2 cleanup, spare skill needed; C37 grid with 1000
horses, then the top 10 and the rule's plan with 4000 fresh horses), for leveling 'today' and 'keep_rarest'.

Usage: python3 -I c25c.py   (writes c25c_results.json, prints the summary)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402
import numba as nb                                                       # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo import horses_fast as F                                         # noqa: E402
from bdo.horses_fast import _pop, _next, _mix, PBITS                     # noqa: E402
import c25                                                               # noqa: E402
import c25b                                                              # noqa: E402


@nb.njit(cache=True)
def _swap_k(out, have, pts, state, w, n, rare, pb, keep_rarest):
    """horses_fast._swap with the desired skill = the second rarest missing wanted skill when keep_rarest and two
    or more are missing (else the rarest missing)."""
    free = ~have & ~(np.int64(1) << out)
    target, first, seen = -1, -1, 0
    for i in rare:
        if (free >> i) & 1:
            seen += 1
            if seen == 1:
                first = i
            if not keep_rarest or seen == 2:
                target = i
                break
    if target < 0:
        target = first
    boost = 1.0 + pb * pts
    tot = 0.0
    for i in range(n):
        if (free >> i) & 1:
            tot += w[i] * boost if i == target else w[i]
    if tot == 0.0:
        return -1, have, state
    state, r = _next(state)
    x = r * tot
    new = -1
    for i in range(n):
        if (free >> i) & 1:
            new = i
            x -= w[i] * boost if i == target else w[i]
            if x < 0:
                break
    have = (have & ~(np.int64(1) << out)) | (np.int64(1) << new)
    return new, have, state


@nb.njit(cache=True)
def _level30_k(r, seed, w, n, W, M, st, swap_from, spend_cap, lmask, fod, cyc, rare, pb, switch_at, keep_rarest):
    a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
    b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
    state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
    have = lmask
    spent = 0
    pts = 0
    latched = False
    for lvl in range(1, 30):
        su = 0.0
        for i in range(n):
            if not (have >> i) & 1:
                su += w[i]
        k = 0.0
        if su > 0:
            k = min(M / (su + W), 1.0 / su)
        state, x = _next(state)
        for i in range(n):
            if not (have >> i) & 1:
                x -= k * w[i]
                if x < 0:
                    have |= np.int64(1) << i
                    break
        if lvl + 1 < swap_from or spent >= spend_cap:
            continue
        if st == 7 and _pop(have) >= switch_at:
            latched = True
        if st == 1 or (st == 7 and not latched):
            for s in fod:
                if (have >> s) & 1 and spent < spend_cap:
                    nw, have, state = _swap_k(s, have, pts, state, w, n, rare, pb, keep_rarest)
                    if nw >= 0:
                        spent += 1
                        pts += 1
        elif st == 6 or st == 7:
            if cyc >= 0 and (have >> cyc) & 1 and spent < spend_cap:
                nw, have, state = _swap_k(cyc, have, pts, state, w, n, rare, pb, keep_rarest)
                if nw >= 0:
                    spent += 1
                    pts += 1
    return have, spent, pts


@nb.njit(cache=True, parallel=True)
def _many30_k(runs, seed, w, n, W, M, st, swap_from, spend_cap, lmask, fod, cyc, rare, pb, switch_at, keep_rarest):
    S = np.empty(runs, np.int64)
    base = np.empty(runs, np.int64)
    pts = np.empty(runs, np.int64)
    for r in nb.prange(runs):
        S[r], base[r], pts[r] = _level30_k(r, seed, w, n, W, M, st, swap_from, spend_cap, lmask, fod, cyc, rare, pb,
                                           switch_at, keep_rarest)
    return S, base, pts


def goal_values(plans, ev, runs, seed, g, nW, keep_rarest):
    """As c25b.goal_values, with the leveling swaps' targeting per keep_rarest."""
    w, n, W, M = ev.args
    lmask, wmask, fod, cyc, order, rare = ev.masks
    hk, hb, hp, hc = [], [], [], []
    for i, (st, lv, cap, T) in enumerate(plans):
        cp = cap if st != "at30" else 0
        S, b, pts = _many30_k(runs, seed, w, n, W, M, F.CODES[st], lv, cp, lmask, fod, cyc, rare, 0.25, T,
                              keep_rarest)
        hk.append((S << PBITS) | pts)
        hb.append(b)
        hp.append(np.full(runs, i, np.int64))
        hc.append(np.full(runs, cp, np.int64))
    hk, hb, hp, hc = map(np.concatenate, (hk, hb, hp, hc))
    spare = F._popcounts(hk >> PBITS) >= nW
    hp = np.where(spare, hp, len(plans))
    acc = c25.le1_values(hk, hb, hp, hc, len(plans) + 1, c25b.C, g, True)[:len(plans)] / runs
    caps = np.array([0 if p[0] == "at30" else p[2] for p in plans])
    acc[np.arange(c25b.C + 1)[None, :] < caps[:, None]] = np.nan
    return acc


def main():
    d = H.load_data()
    out = []
    for hn in c25.HORSES:
        h = H.get_horse(d, hn)
        for tr in c25.TRAININGS:
            t0 = time.time()
            ev = F.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), max_budget=c25b.C)
            w, n, W, M = ev.args
            lmask, wmask, fod, cyc, order, rare = ev.masks
            g, nW = (w, n, wmask, order, rare), _pop(int(wmask))
            row = {"horse": hn, "training": tr, "budgets": {}}
            v1 = {kr: goal_values(c25b.PLANS, ev, c25b.RUNS1, 4101, g, nW, kr) for kr in (False, True)}
            for B in c25.BUDGETS:
                rule = H.rule_plan(B)
                cand = {rule}
                for kr in (False, True):
                    col = np.where(np.isnan(v1[kr][:, B]), -1, v1[kr][:, B])
                    cand |= {c25b.PLANS[j] for j in np.argsort(-col)[:c25b.TOP]}
                cand = sorted(cand)
                cell = {}
                for kr, name in ((False, "today"), (True, "keep_rarest")):
                    v2 = goal_values(cand, ev, c25b.RUNS2, 4102, g, nW, kr)[:, B]
                    j = int(np.nanargmax(v2))
                    cell[name] = {"rule": float(v2[cand.index(rule)]), "best": float(v2[j]), "best_plan": list(cand[j])}
                row["budgets"][B] = cell
            out.append(row)
            print(f"{hn[:12]:<12} {tr:<10} {time.time() - t0:.0f}s", flush=True)
    json.dump(out, open(os.path.join(HERE, "c25c_results.json"), "w"), indent=1)
    print("\nfull set with the Selection Coupon at the end (adapted cleanup); leveling swaps targeting today vs keeping "
          "the rarest\ncase | budget | rule's plan: today / keep_rarest (diff) | best plan: today / keep_rarest (diff) | best plan with keep_rarest")
    for row in out:
        for B, c in row["budgets"].items():
            t, k = c["today"], c["keep_rarest"]
            print(f"{row['horse'].split(' (')[0][:10]} {row['training']:<10} | {B} | {100 * t['rule']:.1f} / "
                  f"{100 * k['rule']:.1f} ({100 * (k['rule'] - t['rule']):+.1f}) | {100 * t['best']:.1f} / "
                  f"{100 * k['best']:.1f} ({100 * (k['best'] - t['best']):+.1f}) | {H.plan_name(tuple(k['best_plan']), B)}")


if __name__ == "__main__":
    main()
