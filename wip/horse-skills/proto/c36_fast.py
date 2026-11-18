"""C36 v2-vs-v0-hard: mixes of classic Coursier (V0: swap Hind Kick and Fore Chop) and V2 (swap only Hind Kick).

Same engine as bdo/horses_fast.py (imported), with extra leveling strategies, each level choosing V0 or V2 swaps:
  1  V0                       6  V2
  10 V0 until level xa, then V2         11 V2 until level xa, then V0
  12 V0 until the horse holds >= xb skills (then V2 for good)
  13 V2, but V0 on levels >= xa while the horse holds < xb skills (falling behind)
  14 V0 until at most xb travel skills are missing, then V2 (C38)
  15 V0 until at most xb travel skills are missing and the horse holds >= xa skills, then V2 (C38)
The exact cleanup table stores only the full-set chance (G), to fit budgets up to 50 in memory.
"""
import numpy as np
import numba as nb
from numba import types
from numba.typed import Dict

from bdo import horses as H
from bdo.horses_fast import _next, _mix, _pop, _swap, _slot, _trans, _explore, PBITS


@nb.njit(cache=True)
def _level30x(r, seed, w, n, W, M, st, swap_from, spend_cap, xa, xb, lmask, wmask, fod, cyc, rare, pb, max_level):
    a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
    b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
    state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
    have = lmask
    spent = 0
    pts = 0
    latched = False
    for lvl in range(1, max_level):
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
        reached = lvl + 1
        if reached < swap_from or spent >= spend_cap or st == 0:
            continue
        held = _pop(have)
        v0 = False
        if st == 1:
            v0 = True
        elif st == 10:
            v0 = reached < xa
        elif st == 11:
            v0 = reached >= xa
        elif st == 12:
            if held >= xb:
                latched = True
            v0 = not latched
        elif st == 13:
            v0 = reached >= xa and held < xb
        elif st == 14 or st == 15:
            # 14: V0 until at most xb travel skills are missing (then V2 for good);
            # 15: same, but only once the horse also holds >= xa skills
            missing = _pop(wmask) - _pop(have & wmask)
            if missing <= xb and (st == 14 or held >= xa):
                latched = True
            v0 = not latched
        if v0:
            for s in fod:
                if (have >> s) & 1 and spent < spend_cap:
                    nw, have, state = _swap(s, have, pts, state, w, n, rare, pb)
                    if nw >= 0:
                        spent += 1
                        pts += 1
        elif cyc >= 0 and (have >> cyc) & 1 and spent < spend_cap:
            nw, have, state = _swap(cyc, have, pts, state, w, n, rare, pb)
            if nw >= 0:
                spent += 1
                pts += 1
    return have, spent, pts


@nb.njit(cache=True, parallel=True)
def _many30x(runs, seed, w, n, W, M, st, swap_from, spend_cap, xa, xb, lmask, wmask, fod, cyc, rare, pb, max_level):
    S = np.empty(runs, np.int64)
    base = np.empty(runs, np.int64)
    pts = np.empty(runs, np.int64)
    for r in nb.prange(runs):
        a, b, c = _level30x(r, seed, w, n, W, M, st, swap_from, spend_cap, xa, xb, lmask, wmask, fod, cyc, rare, pb,
                            max_level)
        S[r] = a
        base[r] = b
        pts[r] = c
    return S, base, pts


@nb.njit(cache=True)
def _fillG(keys, d, G, C, w, n, wmask, order, rare, pb):
    nW = _pop(wmask)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for k in keys:
        r = d[k]
        S = k >> PBITS
        p = k & ((1 << PBITS) - 1)
        if _pop(S & wmask) == nW:
            for c in range(C + 1):
                G[r, c] = 1.0
            continue
        G[r, 0] = 0.0
        out = _slot(S, wmask, order)
        m = 0
        if out >= 0:
            m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
        for c in range(1, C + 1):
            g = 0.0
            for j in range(m):
                k2 = (nxt[j] << PBITS) | (p + 1)
                if k2 in d:
                    g += prb[j] * G[d[k2], c - 1]
            G[r, c] = g


@nb.njit(cache=True)
def _rows(keys, d):
    out = np.empty(len(keys), np.int64)
    for i in range(len(keys)):
        out[i] = d[keys[i]]
    return out


class TableG:
    def __init__(self, w, wmask, order, rare, C, pb=0.25):
        self.w = np.array(w, np.float64)
        self.n, self.wmask, self.C, self.pmax, self.pb = len(w), int(wmask), C, C, pb
        self.order = np.array(order, np.int64)
        self.rare = np.array(rare, np.int64)
        self.d = Dict.empty(key_type=types.int64, value_type=types.int64)
        self.rows = 0
        self.G = np.zeros((1 << 14, C + 1), np.float32)
        self.known = set()

    def ensure(self, keys):
        # skip keys already in the table with a Python-side set (asking the numba dict costs ~30 ms per call)
        todo = [k for k in np.unique(keys).tolist() if k not in self.known]
        if not todo:
            return
        new = _explore(np.array(todo, np.int64), self.d, self.rows, self.pmax, self.w, self.n, self.wmask, self.order,
                       self.rare, self.pb)
        self.known.update(new.tolist())
        if not len(new):
            return
        need = self.rows + len(new)
        if need > len(self.G):
            a = np.zeros((max(need, 2 * len(self.G)), self.C + 1), np.float32)
            a[:self.rows] = self.G[:self.rows]
            self.G = a
        self.rows = need
        new = new[np.argsort(-(new & ((1 << PBITS) - 1)), kind="stable")]
        _fillG(new, self.d, self.G, self.C, self.w, self.n, self.wmask, self.order, self.rare, self.pb)


class Evaluator:
    def __init__(self, horse, M, C=50, table=None):
        pool = list(horse.weights)
        idx = {s: i for i, s in enumerate(pool)}
        w = [float(horse.weights[s]) for s in pool]
        wanted = set(H.TRAVEL_SET) & set(pool)
        fod = [s for s in H.CLASSIC_FODDER if s in idx and s not in wanted]
        cyc = H._cycle_skill(fod, horse.weights)
        order = sorted(range(len(pool)), key=lambda i: (w[i], i))
        wmask = sum(1 << idx[s] for s in wanted)
        self.rare = [i for i in order if wmask >> i & 1]
        self.a = (np.array(w), len(pool), float(horse.W), float(M), np.int64(0), np.int64(wmask),
                  np.array([idx[s] for s in fod], np.int64), idx[cyc] if cyc else -1, np.array(self.rare, np.int64))
        self.C = C
        self.table = table or TableG(w, wmask, order, self.rare, C)

    def plan(self, st, swap_from, cap, xa=0, xb=0, runs=1000, seed=1):
        w, n, W, M, lmask, wmask, fod, cyc, rare = self.a
        S, base, pts = _many30x(runs, seed, w, n, W, M, st, swap_from, cap if st else 0, xa, xb, lmask, wmask, fod,
                                cyc, rare, 0.25, 30)
        keys = (S << PBITS) | pts
        self.table.ensure(keys)
        rows = _rows(keys, self.table.d)
        out = np.full(self.C + 1, np.nan)
        for B in range(cap if st else 0, self.C + 1):
            out[B] = self.table.G[rows, np.minimum(B - base, self.C)].mean()
        return out
