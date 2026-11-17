"""Prototype: faster versions of bdo.horses.simulate_plan (same model, same plan rules, same output).

- simulate_plan_py: plain Python, skills as bit flags and precomputed weights (no dependency).
- simulate_plan_nb: numba-compiled loop over horses; parallel=True spreads horses over the cores. Each horse
  has its own random generator seeded from (seed, horse index), so results don't depend on the core count.

Both differ from bdo.horses.simulate_plan only in their random numbers (and in breaking exact weight ties by
skill order instead of set order), so they're compared statistically, not number for number.
"""
import math
import random

import numpy as np

from bdo import horses as H

STRAT = {"natural": 4, "at30": 0, "coursier": 1, "once": 2, "hard": 3}


def _prepare(horse, strategy, learned, wanted, fodder):
    pool = list(horse.weights)
    idx = {s: i for i, s in enumerate(pool)}
    w = [float(horse.weights[s]) for s in pool]
    wanted = set(H.TRAVEL_SET if wanted is None else wanted) & set(pool)
    fodder = [s for s in (H.CLASSIC_FODDER if fodder is None else fodder) if s in idx and s not in wanted]
    wmask = 0
    for s in wanted:
        wmask |= 1 << idx[s]
    lmask = 0
    for s in learned:
        if s in idx:
            lmask |= 1 << idx[s]
    order = sorted(range(len(pool)), key=lambda i: (w[i], i))       # rarest first, ties by skill order
    return pool, w, wmask, lmask, [idx[s] for s in fodder], order, len(wanted)


def _result(full_n, wanted_sum, needed, counts, runs, spend_cap, nb, n_wanted):
    needed = sorted(needed)
    counts = sorted(counts)
    return {"full": [full_n[B] / runs if B >= spend_cap else None for B in range(nb)],
            "wanted": [wanted_sum[B] / runs if B >= spend_cap else None for B in range(nb)],
            "skills": sum(counts) / runs, "needed": needed, "skill_counts": counts, "wanted_total": n_wanted}


# --- plain Python ---------------------------------------------------------------------------------------------

def simulate_plan_py(horse, M, strategy, swap_from=1, spend_cap=0, max_budget=60, tickets=0, start_level=1,
                     learned=(), wanted=None, fodder=None, point_bonus=0.25, points=0, runs=4000, seed=1,
                     max_level=30):
    pool, w, wmask, lmask, fod, order, n_wanted = _prepare(horse, strategy, learned, wanted, fodder)
    n = len(pool)
    W = horse.W
    st = STRAT[strategy]
    if st == 0:
        spend_cap = 0
    rnd = random.Random(seed).random
    nb = max_budget + 1
    full_n, wanted_sum = [0] * nb, [0] * nb
    needed, counts = [], []
    bits = [1 << i for i in range(n)]
    rare_wanted = [i for i in order if wmask >> i & 1]                # wanted skills, rarest first
    popcount = int.bit_count if hasattr(int, "bit_count") else (lambda x: bin(x).count("1"))
    for _ in range(runs):
        have, spent, t, pts = lmask, 0, tickets, points

        def swap(out):
            nonlocal have, spent, pts
            free = ~have & ~bits[out]
            target = -1
            for i in rare_wanted:
                if free >> i & 1:
                    target = i
                    break
            tot = 0.0
            for i in range(n):
                if free >> i & 1:
                    tot += w[i] * (1 + point_bonus * pts) if i == target else w[i]
            if tot == 0:
                return -1
            x = rnd() * tot
            new = -1
            for i in range(n):
                if free >> i & 1:
                    new = i
                    x -= w[i] * (1 + point_bonus * pts) if i == target else w[i]
                    if x < 0:
                        break
            have = (have & ~bits[out]) | bits[new]
            spent += 1
            pts += 1
            return new

        for lvl in range(start_level, max_level):
            while True:
                su = 0.0
                for i in range(n):
                    if not have >> i & 1:
                        su += w[i]
                k = min(M / (su + W), 1 / su) if su else 0
                x, got = rnd(), -1
                for i in range(n):
                    if not have >> i & 1:
                        x -= k * w[i]
                        if x < 0:
                            got = i
                            break
                if got >= 0 or t == 0:
                    break
                t -= 1
            if got >= 0:
                have |= bits[got]
            if lvl + 1 < swap_from or spent >= spend_cap:
                continue
            if st == 1:
                for s in fod:
                    if have >> s & 1 and spent < spend_cap:
                        swap(s)
            elif st == 2:
                if lvl + 1 == swap_from > 1:
                    todo = [i for i in order if have >> i & 1 and not wmask >> i & 1]
                else:
                    todo = [got]
                for s in todo:
                    if s >= 0 and not wmask >> s & 1 and have >> s & 1 and spent < spend_cap:
                        swap(s)
            elif st == 3:
                for s in [i for i in order if have >> i & 1 and not wmask >> i & 1]:
                    slot = s
                    while slot >= 0 and not wmask >> slot & 1 and have >> slot & 1 and spent < spend_cap:
                        slot = swap(slot)
        counts.append(popcount(have))
        base = spent
        traj = [popcount(have & wmask)]
        if st != 4:
            for s in [i for i in order if have >> i & 1 and not wmask >> i & 1]:
                slot = s
                while slot >= 0 and not wmask >> slot & 1 and have & wmask != wmask:
                    slot = swap(slot)
                    traj.append(popcount(have & wmask))
                if have & wmask == wmask:
                    break
        done = have & wmask == wmask
        need = base + len(traj) - 1 if done else math.inf
        needed.append(need)
        last = len(traj) - 1
        for B in range(spend_cap, nb):
            if st == 4:
                wanted_sum[B] += traj[0]
                full_n[B] += traj[0] == n_wanted
            else:
                wanted_sum[B] += traj[min(B - base, last)]
                full_n[B] += need <= B
    return _result(full_n, wanted_sum, needed, counts, runs, spend_cap, nb, n_wanted)


# --- numba ----------------------------------------------------------------------------------------------------

try:
    import numba as nb_
except ImportError:                                                     # pragma: no cover
    nb_ = None

if nb_ is not None:
    @nb_.njit(cache=True, inline="always")
    def _next(state):
        # splitmix64: returns (new state, float in [0, 1))
        state = (state + np.uint64(0x9E3779B97F4A7C15))
        z = state
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
        return state, float(z >> np.uint64(11)) * (1.0 / 9007199254740992.0)

    @nb_.njit(cache=True, inline="always")
    def _mix(z):
        # splitmix64 finalizer as a hash: returns (unused, 64-bit scrambled value)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return 0, z ^ (z >> np.uint64(31))

    @nb_.njit(cache=True)
    def _swap(out, have, pts, state, w, n, rare_wanted, point_bonus):
        free = ~have & ~(np.int64(1) << out)
        target = -1
        for i in rare_wanted:
            if (free >> i) & 1:
                target = i
                break
        boost = 1.0 + point_bonus * pts
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

    @nb_.njit(cache=True)
    def _popcount(x):
        c = 0
        while x:
            x &= x - 1
            c += 1
        return c

    @nb_.njit(cache=True)
    def _one_horse(r, seed, w, n, W, M, st, swap_from, spend_cap, max_budget, tickets, start_level, lmask, wmask,
                   fod, order, rare_wanted, point_bonus, points, max_level, traj_out):
        """Plays one horse; fills traj_out (wanted skills after j cleanup coupons, j = 0..max_budget).
        Returns (coupons spent while leveling, coupons needed for the full set or -1, skills at 30)."""
        # independent stream per horse: scramble (seed, r) into a random 64-bit starting point. (Starting points
        # spaced by the generator's own step would make horse r+1 replay horse r's numbers shifted by one.)
        _, a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
        _, b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
        state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
        have = lmask
        spent = 0
        t = tickets
        pts = points
        for lvl in range(start_level, max_level):
            got = -1
            while True:
                su = 0.0
                for i in range(n):
                    if not (have >> i) & 1:
                        su += w[i]
                k = 0.0
                if su > 0:
                    k = min(M / (su + W), 1.0 / su)
                state, x = _next(state)
                got = -1
                for i in range(n):
                    if not (have >> i) & 1:
                        x -= k * w[i]
                        if x < 0:
                            got = i
                            break
                if got >= 0 or t == 0:
                    break
                t -= 1
            if got >= 0:
                have |= np.int64(1) << got
            if lvl + 1 < swap_from or spent >= spend_cap:
                continue
            if st == 1:
                for s in fod:
                    if (have >> s) & 1 and spent < spend_cap:
                        nw, have, state = _swap(s, have, pts, state, w, n, rare_wanted, point_bonus)
                        if nw >= 0:
                            spent += 1
                            pts += 1
            elif st == 2:
                if lvl + 1 == swap_from and swap_from > 1:
                    todo = np.empty(n, np.int64)                # snapshot: skills got by these swaps aren't redone
                    m = 0
                    for s in order:
                        if (have >> s) & 1 and not (wmask >> s) & 1:
                            todo[m] = s
                            m += 1
                    for q in range(m):
                        s = todo[q]
                        if (have >> s) & 1 and not (wmask >> s) & 1 and spent < spend_cap:
                            nw, have, state = _swap(s, have, pts, state, w, n, rare_wanted, point_bonus)
                            if nw >= 0:
                                spent += 1
                                pts += 1
                elif got >= 0 and not (wmask >> got) & 1 and (have >> got) & 1 and spent < spend_cap:
                    nw, have, state = _swap(got, have, pts, state, w, n, rare_wanted, point_bonus)
                    if nw >= 0:
                        spent += 1
                        pts += 1
            elif st == 3:
                todo = np.empty(n, np.int64)
                m = 0
                for s in order:
                    if (have >> s) & 1 and not (wmask >> s) & 1:
                        todo[m] = s
                        m += 1
                for q in range(m):
                    slot = todo[q]
                    while slot >= 0 and not (wmask >> slot) & 1 and (have >> slot) & 1 and spent < spend_cap:
                        slot, have, state = _swap(slot, have, pts, state, w, n, rare_wanted, point_bonus)
                        if slot >= 0:
                            spent += 1
                            pts += 1
        skills = _popcount(have)
        cur = _popcount(have & wmask)
        traj_out[0] = cur
        j = 0
        if st != 4:
            todo = np.empty(n, np.int64)
            m = 0
            for s in order:
                if (have >> s) & 1 and not (wmask >> s) & 1:
                    todo[m] = s
                    m += 1
            for q in range(m):
                slot = todo[q]
                while slot >= 0 and not (wmask >> slot) & 1 and (have & wmask) != wmask and j < 100000:
                    slot, have, state = _swap(slot, have, pts, state, w, n, rare_wanted, point_bonus)
                    pts += 1
                    j += 1
                    if j <= max_budget:
                        traj_out[j] = _popcount(have & wmask)
                if (have & wmask) == wmask:
                    break
        last = min(j, max_budget)
        for q in range(last + 1, max_budget + 1):
            traj_out[q] = traj_out[last]
        need = spent + j if (have & wmask) == wmask else -1
        return spent, need, skills

    @nb_.njit(cache=True, parallel=True)
    def _many(runs, seed, w, n, W, M, st, swap_from, spend_cap, max_budget, tickets, start_level, lmask, wmask,
              fod, order, rare_wanted, point_bonus, points, max_level):
        trajs = np.zeros((runs, max_budget + 1), np.int64)
        base = np.zeros(runs, np.int64)
        need = np.zeros(runs, np.int64)
        skills = np.zeros(runs, np.int64)
        for r in nb_.prange(runs):
            b, nd, sk = _one_horse(r, seed, w, n, W, M, st, swap_from, spend_cap, max_budget, tickets,
                                   start_level, lmask, wmask, fod, order, rare_wanted, point_bonus, points,
                                   max_level, trajs[r])
            base[r] = b
            need[r] = nd
            skills[r] = sk
        return trajs, base, need, skills


def simulate_plan_nb(horse, M, strategy, swap_from=1, spend_cap=0, max_budget=60, tickets=0, start_level=1,
                     learned=(), wanted=None, fodder=None, point_bonus=0.25, points=0, runs=4000, seed=1,
                     max_level=30):
    pool, w, wmask, lmask, fod, order, n_wanted = _prepare(horse, strategy, learned, wanted, fodder)
    st = STRAT[strategy]
    if st == 0:
        spend_cap = 0
    rare_wanted = [i for i in order if wmask >> i & 1]
    trajs, base, need, skills = _many(
        runs, seed, np.array(w), len(pool), float(horse.W), float(M), st, swap_from, spend_cap, max_budget,
        tickets, start_level, np.int64(lmask), np.int64(wmask), np.array(fod or [-1], np.int64)[:len(fod)],
        np.array(order, np.int64), np.array(rare_wanted or [-1], np.int64)[:len(rare_wanted)],
        float(point_bonus), points, max_level)
    nb = max_budget + 1
    full_n, wanted_sum = [0] * nb, [0] * nb
    Bs = np.arange(nb)
    if st == 4:
        wanted_sum = [int(trajs[:, 0].sum())] * nb
        full_n = [int((trajs[:, 0] == n_wanted).sum())] * nb
    else:
        for B in range(spend_cap, nb):
            j = np.clip(B - base, 0, max_budget)
            wanted_sum[B] = int(trajs[np.arange(runs), j].sum())
            full_n[B] = int(((need >= 0) & (need <= B)).sum())
    needed = [float(x) if x >= 0 else math.inf for x in need]
    return _result(full_n, wanted_sum, needed, skills.tolist(), runs, spend_cap, nb, n_wanted)
