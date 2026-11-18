"""C27: best possible level-30 cleanup, computed exactly.

At each coupon: choose which unwanted skill to swap out (any held) and which missing wanted skill to mark as
desired (any). For held skills S, points p and c coupons left:
  Gopt[c] = best chance of ending with every wanted skill   (goal: full set)
  Hopt[c] = best expected number of wanted skills at the end (goal: most travel skills)
Each goal has its own best choices, and they can depend on c.
Also measured: the best value when the desired skill is forced to be the rarest missing one (any slot), and when the
slot is forced to be the rarest unwanted held (any desired), to see which choice matters.
"""
import numpy as np
import numba as nb
from numba import types
from numba.typed import Dict

from table_nb import PBITS, _pop

MAXA = 7 * 13            # actions: unwanted held x missing wanted


@nb.njit(cache=True)
def _actions(S, wmask, n, order, rare, outs, tgts):
    """Fills (slot, desired) pairs; returns count. Index 0 is always the 'rarest/rarest' action."""
    m = 0
    r_out = -1
    for i in order:
        if (S >> i) & 1 and not (wmask >> i) & 1:
            r_out = i
            break
    r_tgt = -1
    for i in rare:
        if not (S >> i) & 1:
            r_tgt = i
            break
    if r_out < 0:
        return 0
    outs[0] = r_out
    tgts[0] = r_tgt
    m = 1
    for i in order:
        if (S >> i) & 1 and not (wmask >> i) & 1:
            for j in rare:
                if not (S >> j) & 1:
                    if i == r_out and j == r_tgt:
                        continue
                    outs[m] = i
                    tgts[m] = j
                    m += 1
    return m


@nb.njit(cache=True)
def _trans_t(S, p, out, target, w, n, pb, nxt, prb):
    full = (np.int64(1) << n) - 1
    free = ~S & ~(np.int64(1) << out) & full
    boost = 1.0 + pb * p
    tot = 0.0
    for i in range(n):
        if (free >> i) & 1:
            tot += w[i] * boost if i == target else w[i]
    if tot == 0.0:
        return 0
    m = 0
    for i in range(n):
        if (free >> i) & 1:
            nxt[m] = (S & ~(np.int64(1) << out)) | (np.int64(1) << i)
            prb[m] = (w[i] * boost if i == target else w[i]) / tot
            m += 1
    return m


@nb.njit(cache=True)
def _explore(starts, d, n_rows, pmax, w, n, wmask, order, rare, pb):
    new = []
    stack = [np.int64(0)] * 0
    for k in starts:
        stack.append(k)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    outs = np.empty(MAXA, np.int64)
    tgts = np.empty(MAXA, np.int64)
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
        na = _actions(S, wmask, n, order, rare, outs, tgts)
        for a in range(na):
            m = _trans_t(S, p, outs[a], tgts[a], w, n, pb, nxt, prb)
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
    """G/H: best chance of the full set / best expected wanted skills, over every (slot, desired) choice."""
    nW = _pop(wmask)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    outs = np.empty(MAXA, np.int64)
    tgts = np.empty(MAXA, np.int64)
    for k in keys:
        r = d[k]
        S = k >> PBITS
        p = k & ((1 << PBITS) - 1)
        hw = _pop(S & wmask)
        if hw == nW:
            for c in range(C + 1):
                G[r, c] = 1.0
                H[r, c] = nW
            continue
        G[r, 0] = 0.0
        H[r, 0] = hw
        na = _actions(S, wmask, n, order, rare, outs, tgts)
        for c in range(1, C + 1):
            bg = 0.0
            bh = float(hw)
            for a in range(na):
                m = _trans_t(S, p, outs[a], tgts[a], w, n, pb, nxt, prb)
                g = 0.0
                h = 0.0
                for j in range(m):
                    k2 = (nxt[j] << PBITS) | (p + 1)
                    if k2 in d:
                        r2 = d[k2]
                        g += prb[j] * G[r2, c - 1]
                        h += prb[j] * H[r2, c - 1]
                    else:
                        h += prb[j] * _pop(nxt[j] & wmask)
                if g > bg:
                    bg = g
                if h > bh:
                    bh = h
            G[r, c] = bg
            H[r, c] = bh


class OptTable:
    def __init__(self, w, wmask, order, rare, C=40, pmax=40, point_bonus=0.25):
        self.w = np.array(w, np.float64)
        self.n, self.wmask, self.C, self.pmax, self.pb = len(w), int(wmask), C, pmax, point_bonus
        self.order = np.array(order, np.int64)
        self.rare = np.array(rare, np.int64)
        self.d = Dict.empty(key_type=types.int64, value_type=types.int64)
        self.rows = 0
        self.arr = {k: np.zeros((1 << 16, C + 1), np.float32) for k in ("G", "H")}

    def ensure(self, keys):
        new = _explore(np.unique(np.asarray(keys, np.int64)), self.d, self.rows, self.pmax, self.w, self.n,
                       self.wmask, self.order, self.rare, self.pb)
        if not len(new):
            return 0
        need = self.rows + len(new)
        if need > len(self.arr["G"]):
            cap = max(need, 2 * len(self.arr["G"]))
            for name in list(self.arr):
                a = np.zeros((cap, self.C + 1), np.float32)
                a[:self.rows] = self.arr[name][:self.rows]
                self.arr[name] = a
        self.rows = need
        p = new & ((1 << PBITS) - 1)
        new = new[np.argsort(-p, kind="stable")]
        A = self.arr
        _fill(new, self.d, A["G"], A["H"], self.C, self.w, self.n, self.wmask,
              self.order, self.rare, self.pb)
        return len(new)
