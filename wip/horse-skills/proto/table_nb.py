"""Prototype (C26): shared exact cleanup table in numba, and plan evaluation = simulated leveling + exact cleanup.

Cleanup rule: always swap the rarest unwanted skill held; desired skill = rarest missing wanted skill.
For a held-skill set S with p Skill Change Points (key = S << 7 | p), with c coupons left:
  G[c] = chance of ending with every wanted skill,  H[c] = expected number of wanted skills at the end.
The table depends only on the horse's weights, the wanted set and the point bonus (not on Training or boosts),
so one table serves every plan, Training level and boost setting of a horse. Entries are exact (no
approximation); the table just grows as plans reach new level-30 states.

Leveling strategies: 0 at30, 1 coursier, 2 once, 3 hard, 4 natural (no cleanup),
5 coursier V1 (swap Hind Kick / Fore Chop only while the other one is learned: no loop),
6 coursier V2 (only ever swap the first fodder skill, Hind Kick),
7 cycle Fore Chop instead, 8 cycle whichever of the two is learned first, 9 V2 + every other unwanted skill swapped once.
"""
import numpy as np
import numba as nb
from numba import types
from numba.typed import Dict

import sim_fast as F

PBITS = 7                      # points stored in the low 7 bits of the key (p <= 127)


@nb.njit(cache=True, inline="always")
def _pop(x):
    c = 0
    while x:
        x &= x - 1
        c += 1
    return c


@nb.njit(cache=True)
def _slot(S, wmask, order):
    for i in order:
        if (S >> i) & 1 and not (wmask >> i) & 1:
            return i
    return -1


@nb.njit(cache=True)
def _trans(S, p, out, w, n, rare, pb, nxt, prb):
    full = (np.int64(1) << n) - 1
    free = ~S & ~(np.int64(1) << out) & full
    target = -1
    for i in rare:
        if (free >> i) & 1:
            target = i
            break
    boost = 1.0 + pb * p
    tot = 0.0
    for i in range(n):
        if (free >> i) & 1:
            tot += w[i] * boost if i == target else w[i]
    m = 0
    if tot == 0.0:
        return 0
    for i in range(n):
        if (free >> i) & 1:
            nxt[m] = (S & ~(np.int64(1) << out)) | (np.int64(1) << i)
            prb[m] = (w[i] * boost if i == target else w[i]) / tot
            m += 1
    return m


@nb.njit(cache=True)
def _explore(starts, d, n_rows, pmax, w, n, wmask, order, rare, pb):
    """Adds to d every key reachable from starts (p <= pmax) not yet in d; returns the new keys."""
    new = []
    stack = [np.int64(0)] * 0
    for k in starts:
        stack.append(k)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    row = n_rows
    while len(stack):
        k = stack.pop()
        if k in d:
            continue
        d[k] = row
        row += 1
        new.append(k)
        S = k >> PBITS
        p = k & ((1 << PBITS) - 1)
        if (S & wmask) == wmask or p >= pmax:
            continue
        out = _slot(S, wmask, order)
        if out < 0:
            continue
        m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
        for j in range(m):
            k2 = (nxt[j] << PBITS) | (p + 1)
            if k2 not in d:
                stack.append(k2)
    res = np.empty(len(new), np.int64)
    for i in range(len(new)):
        res[i] = new[i]
    return res


@nb.njit(cache=True)
def _fill(keys, d, G, H, C, w, n, wmask, order, rare, pb):
    """Computes G and H rows for keys (sorted by p, highest first: successors are always done before)."""
    nW = _pop(wmask)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for k in keys:
        r = d[k]
        S = k >> PBITS
        p = k & ((1 << PBITS) - 1)
        have_w = _pop(S & wmask)
        if have_w == nW:
            for c in range(C + 1):
                G[r, c] = 1.0
                H[r, c] = nW
            continue
        G[r, 0] = 0.0
        H[r, 0] = have_w
        out = _slot(S, wmask, order)
        m = 0
        if out >= 0:
            m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
        for c in range(1, C + 1):
            g = 0.0
            h = 0.0
            if m == 0:
                h = have_w
            for j in range(m):
                k2 = (nxt[j] << PBITS) | (p + 1)
                if k2 in d:
                    r2 = d[k2]
                    g += prb[j] * G[r2, c - 1]
                    h += prb[j] * H[r2, c - 1]
                else:                              # beyond pmax: only reached when no coupon is left anyway
                    h += prb[j] * _pop(nxt[j] & wmask)
            G[r, c] = g
            H[r, c] = h


class Table:
    def __init__(self, w, wmask, order, rare, C=40, pmax=100, point_bonus=0.25):
        self.w = np.array(w, np.float64)
        self.n, self.wmask, self.C, self.pmax, self.pb = len(w), int(wmask), C, pmax, point_bonus
        self.order = np.array(order, np.int64)
        self.rare = np.array(rare, np.int64)
        self.d = Dict.empty(key_type=types.int64, value_type=types.int64)
        self.rows = 0
        self.G = np.zeros((1 << 16, C + 1), np.float32)
        self.H = np.zeros((1 << 16, C + 1), np.float32)

    def ensure(self, keys):
        new = _explore(np.unique(np.asarray(keys, np.int64)), self.d, self.rows, self.pmax, self.w, self.n,
                       self.wmask, self.order, self.rare, self.pb)
        if not len(new):
            return 0
        need = self.rows + len(new)
        if need > len(self.G):
            cap = max(need, 2 * len(self.G))
            for name in ("G", "H"):
                a = np.zeros((cap, self.C + 1), np.float32)
                a[:self.rows] = getattr(self, name)[:self.rows]
                setattr(self, name, a)
        self.rows = need
        p = new & ((1 << PBITS) - 1)
        new = new[np.argsort(-p, kind="stable")]
        _fill(new, self.d, self.G, self.H, self.C, self.w, self.n, self.wmask, self.order, self.rare, self.pb)
        return len(new)

    def rows_of(self, keys):
        return _rows(np.asarray(keys, np.int64), self.d)


@nb.njit(cache=True)
def _rows(keys, d):
    out = np.empty(len(keys), np.int64)
    for i in range(len(keys)):
        out[i] = d[keys[i]]
    return out


# --- leveling only -------------------------------------------------------------------------------------------

@nb.njit(cache=True)
def _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod, order, rare,
             point_bonus, points, max_level):
    """Same leveling as sim_fast._one_horse (same random numbers), stopping before the level-30 cleanup.
    Returns (held skills at 30, coupons spent while leveling, Skill Change Points at 30)."""
    _, a = F._mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
    _, b = F._mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
    state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
    have = lmask
    spent = 0
    t = tickets
    pts = points
    first = -1                                   # first fodder skill learned (strategy 8)
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
            state, x = F._next(state)
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
            if first < 0:
                for q in range(len(fod)):
                    if fod[q] == got:
                        first = got
        if lvl + 1 < swap_from or spent >= spend_cap:
            continue
        if st == 7 or st == 8 or st == 9:
            # cycle exactly one fodder skill, keep the other(s): 7 = the second one (Fore Chop), 8 = the first one
            # learned, 9 = Hind Kick plus every other unwanted skill swapped once when learned
            cyc = -1
            if st == 7 and len(fod) > 1:
                cyc = fod[1]
            elif st == 8:
                cyc = first
            elif st == 9 and len(fod) > 0:
                cyc = fod[0]
            if cyc >= 0 and (have >> cyc) & 1 and spent < spend_cap:
                nw, have, state = F._swap(cyc, have, pts, state, w, n, rare, point_bonus)
                if nw >= 0:
                    spent += 1
                    pts += 1
            if st == 9 and got >= 0 and got != cyc and not (wmask >> got) & 1 and (have >> got) & 1:
                is_fod = False
                for q in range(len(fod)):
                    if fod[q] == got:
                        is_fod = True
                if not is_fod and spent < spend_cap:
                    nw, have, state = F._swap(got, have, pts, state, w, n, rare, point_bonus)
                    if nw >= 0:
                        spent += 1
                        pts += 1
        elif st == 1 or st == 5 or st == 6:
            nf = len(fod)
            for q in range(nf):
                s = fod[q]
                if st == 6 and q > 0:
                    break
                if st == 5 and nf == 2 and not (have >> fod[1 - q]) & 1:
                    continue                         # V1: only while the other fodder skill is learned
                if (have >> s) & 1 and spent < spend_cap:
                    nw, have, state = F._swap(s, have, pts, state, w, n, rare, point_bonus)
                    if nw >= 0:
                        spent += 1
                        pts += 1
        elif st == 2:
            if lvl + 1 == swap_from and swap_from > 1:
                todo = np.empty(n, np.int64)
                m = 0
                for s in order:
                    if (have >> s) & 1 and not (wmask >> s) & 1:
                        todo[m] = s
                        m += 1
                for q in range(m):
                    s = todo[q]
                    if (have >> s) & 1 and not (wmask >> s) & 1 and spent < spend_cap:
                        nw, have, state = F._swap(s, have, pts, state, w, n, rare, point_bonus)
                        if nw >= 0:
                            spent += 1
                            pts += 1
            elif got >= 0 and not (wmask >> got) & 1 and (have >> got) & 1 and spent < spend_cap:
                nw, have, state = F._swap(got, have, pts, state, w, n, rare, point_bonus)
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
                    slot, have, state = F._swap(slot, have, pts, state, w, n, rare, point_bonus)
                    if slot >= 0:
                        spent += 1
                        pts += 1
    return have, spent, pts


@nb.njit(cache=True, parallel=True)
def _many30(runs, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod, order, rare,
            point_bonus, points, max_level):
    S = np.empty(runs, np.int64)
    base = np.empty(runs, np.int64)
    pts = np.empty(runs, np.int64)
    for r in nb.prange(runs):
        a, b, c = _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod,
                           order, rare, point_bonus, points, max_level)
        S[r] = a
        base[r] = b
        pts[r] = c
    return S, base, pts


STRAT = {"at30": 0, "coursier": 1, "once": 2, "hard": 3, "natural": 4, "coursier_v1": 5, "coursier_v2": 6,
         "cycle_fc": 7, "cycle_first": 8, "v2_once": 9}


class Evaluator:
    """Plans for one horse and Training/boost setting; the cleanup table is shared (pass the same Table)."""

    def __init__(self, horse, M, table=None, max_budget=40, learned=(), wanted=None, fodder=None, points=0,
                 tickets=0, start_level=1, point_bonus=0.25, max_level=30):
        pool, w, wmask, lmask, fod, order, nw = F._prepare(horse, "coursier", learned, wanted, fodder)
        self.rare = [i for i in order if wmask >> i & 1]
        self.args = dict(w=np.array(w), n=len(pool), W=float(horse.W), M=float(M), lmask=np.int64(lmask),
                         wmask=np.int64(wmask), fod=np.array(fod or [-1], np.int64)[:len(fod)],
                         order=np.array(order, np.int64), rare=np.array(self.rare, np.int64))
        self.C, self.points, self.tickets, self.start_level = max_budget, points, tickets, start_level
        self.pb, self.max_level, self.n_wanted = point_bonus, max_level, nw
        # Points never exceed points + max_budget while coupons remain: points at 30 = points + coupons spent
        # leveling, and the cleanup has at most max_budget minus those left. Entries at pmax only need c = 0.
        self.table = table or Table(w, wmask, order, self.rare, C=max_budget, pmax=points + max_budget,
                                    point_bonus=point_bonus)

    def plan(self, strategy, swap_from=1, spend_cap=0, runs=4000, seed=1):
        """{'full': [chance of the full set with B coupons], 'wanted': [expected wanted skills]} for B = 0..C
        (None below spend_cap), plus 'skills' (average skills at 30)."""
        st = STRAT[strategy]
        if st == 0:
            spend_cap = 0
        A = self.args
        S, base, pts = _many30(runs, seed, A["w"], A["n"], A["W"], A["M"], st, swap_from, spend_cap, self.tickets,
                               self.start_level, A["lmask"], A["wmask"], A["fod"], A["order"], A["rare"], self.pb,
                               self.points, self.max_level)
        skills = np.array([bin(int(x)).count("1") for x in S]).mean()
        nb_ = self.C + 1
        if st == 4:
            hw = np.array([bin(int(x) & int(A["wmask"])).count("1") for x in S])
            return {"full": [float((hw == self.n_wanted).mean())] * nb_, "wanted": [float(hw.mean())] * nb_,
                    "skills": float(skills)}
        keys = (S << PBITS) | pts
        self.table.ensure(keys)
        rows = self.table.rows_of(keys)
        full, wanted = [], []
        for B in range(nb_):
            if B < spend_cap:
                full.append(None)
                wanted.append(None)
                continue
            idx = np.minimum(B - base, self.C)
            full.append(float(self.table.G[rows, idx].mean()))
            wanted.append(float(self.table.H[rows, idx].mean()))
        return {"full": full, "wanted": wanted, "skills": float(skills)}
