"""C39 table-sweep: less memory for the exact level-30 cleanup table.

Variants (values per state and coupons left: P(missing <= j) for j < J, then the expected wanted skills H;
J = 1 is what the tool stores today: full-set chance G and H):
  R     reference = the tool's current table: every state x every coupon count kept (rectangular 0..C), a hash map
        from state to row, grown by doubling, filled once per new state and reused across batches.
  L32 / L16   sweep by coupons left: two layers (c - 1, c) over all states, successors precomputed (CSR).
  P32 / P16   sweep by coupon points: states grouped by points level p; levels computed from the highest down,
        keeping two levels in memory, each with its coupon counts 0..bound - p.
  16 = values stored as 16-bit fixed point (probabilities x 65535; H as a fraction of the wanted count).
L and P use sorted key arrays (bisection) instead of the hash map, and only the combinations with
points + coupons left <= bound, bound = starting points + largest budget (here 0 + C). Every value a horse asks for
satisfies it, with or without a points reset (a reset only lowers the points). L and P keep no values between
batches: each batch of plans is simulated first, then one sweep answers all of it.

Workload (like the optimizer): batch 1 = the C37 grid (All at 30; V0, V2 and 'V0 until T learned skills, then V2'
with T 9-16; start levels 2-29; spending caps up to C) with 1000 horses per plan; batch 2 = every 25th plan with
4000 fresh horses; batch 3 = every 250th plan with 4000 fresh horses. All variants see the same horses.

Usage: python3 -I c39.py CASE C VARIANT J OUT_PREFIX     (VARIANT: none, D, R, L32, L16, P32, P16)
  'none' = simulation only (memory baseline); 'D' = hash map only (its memory).
Prints one JSON line: times (s), peak memory (MB), sizes. Saves OUT_PREFIX.npz (per batch: plan x budget x value).
"""
import json
import os
import resource
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402
import numba as nb                                                       # noqa: E402
from numba import types                                                  # noqa: E402
from numba.typed import Dict                                             # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo.horses_fast import _pop, _slot, _trans, _explore, _rows, PBITS  # noqa: E402
import c36_fast as X                                                     # noqa: E402

PMASK = (1 << PBITS) - 1
CASES = {"t8s1": ("T8 example (bdolytics icon horse_71)", "Skilled 1"), "dinea7": ("Mythical Diné", "Artisan 7"),
         "tiny": ("Mythical Diné", "Guru 20")}
ALL_CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30, 35, 40]


def plans_for(C):
    caps = [c for c in ALL_CAPS if c <= C]
    return ([(0, 1, 0, 0, 0)] + [(st, s, c, 0, 0) for st in (1, 6) for s in range(2, 30) for c in caps]
            + [(12, s, c, 0, T) for s in range(2, 30) for c in caps for T in range(9, 17)])


def batches(C, small=False):
    P = plans_for(C)
    if small:
        return [(P[::400], 200, 11)]
    return [(P, 1000, 101), (P[::25], 4000, 202), (P[::250], 4000, 303)]


def simulate(ctx, plans, runs, seed):
    w, n, W, M, lmask, wmask, fod, cyc, rare = ctx
    keys, base, plan, cap = [], [], [], []
    for i, (st, sf, cp, xa, xb) in enumerate(plans):
        S, b, pts = X._many30x(runs, seed, w, n, W, M, st, sf, cp if st else 0, xa, xb, lmask, wmask, fod, cyc, rare,
                               0.25, 30, 1, 0)
        keys.append((S << PBITS) | pts)
        base.append(b)
        plan.append(np.full(runs, i, np.int64))
        cap.append(np.full(runs, cp if st else 0, np.int64))
    return np.concatenate(keys), np.concatenate(base), np.concatenate(plan), np.concatenate(cap)


def codecs(J, nW, q):
    nv = J + 1
    if not q:
        return np.ones(nv), np.ones(nv)
    enc = np.full(nv, 65535.0)
    enc[J] = 65535.0 / nW
    return enc, 1.0 / enc


# --- R: the tool's current table, generalised to J tails ---------------------------------------------------------

@nb.njit(cache=True)
def _fillR(keys, d, V, C, J, w, n, wmask, order, rare, pb):
    nW = _pop(wmask)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for k in keys:
        r = d[k]
        S = k >> PBITS
        p = k & PMASK
        hw = _pop(S & wmask)
        miss = nW - hw
        m = 0
        if miss > 0:
            out = _slot(S, wmask, order)
            if out >= 0:
                m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
        for c in range(C + 1):
            if c == 0 or m == 0:
                for t in range(J):
                    V[r, c, t] = 1.0 if miss <= t else 0.0
                V[r, c, J] = hw
                continue
            for t in range(J + 1):
                V[r, c, t] = 0.0
            for i in range(m):
                k2 = (nxt[i] << PBITS) | (p + 1)
                if k2 in d:
                    r2 = d[k2]
                    for t in range(J + 1):
                        V[r, c, t] += prb[i] * V[r2, c - 1, t]
                else:                          # beyond pmax: only when no coupon is left anyway (as in the tool)
                    V[r, c, J] += prb[i] * _pop(nxt[i] & wmask)


class TableR:
    def __init__(self, ctx, C, J):
        w, n, W, M, lmask, wmask, fod, cyc, rare = ctx
        self.w, self.n, self.wmask, self.rare = w, n, int(wmask), rare
        self.order = np.array(sorted(range(n), key=lambda i: (w[i], i)), np.int64)
        self.C, self.J, self.pmax = C, J, C
        self.d = Dict.empty(key_type=types.int64, value_type=types.int64)
        self.rows = 0
        self.V = np.zeros((1 << 14, C + 1, J + 1), np.float32)

    def ensure(self, keys):
        new = _explore(np.unique(keys), self.d, self.rows, self.pmax, self.w, self.n, self.wmask, self.order,
                       self.rare, 0.25)
        if not len(new):
            return
        need = self.rows + len(new)
        if need > len(self.V):                 # same growth as the tool: double the capacity
            a = np.zeros((max(need, 2 * len(self.V)), self.C + 1, self.J + 1), np.float32)
            a[:self.rows] = self.V[:self.rows]
            self.V = a
        self.rows = need
        new = new[np.argsort(-(new & PMASK), kind="stable")]
        _fillR(new, self.d, self.V, self.C, self.J, self.w, self.n, self.wmask, self.order, self.rare, 0.25)


@nb.njit(cache=True)
def _accR(rows, base, plan, cap, V, C, acc):
    for i in range(len(rows)):
        for B in range(max(cap[i], base[i]), C + 1):
            for t in range(acc.shape[2]):
                acc[plan[i], B, t] += V[rows[i], B - base[i], t]


# --- shared by L and P: states grouped by points level ------------------------------------------------------------

@nb.njit(cache=True)
def _succ(keys, bound, w, n, wmask, order, rare, pb):
    """Successor keys (points p + 1) of the states that can still use a coupon (p < bound)."""
    out = np.empty(len(keys) * n, np.int64)
    m_tot = 0
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for k in keys:
        S = k >> PBITS
        p = k & PMASK
        if (S & wmask) == wmask or p >= bound:
            continue
        o = _slot(S, wmask, order)
        if o < 0:
            continue
        m = _trans(S, p, o, w, n, rare, pb, nxt, prb)
        for i in range(m):
            out[m_tot] = (nxt[i] << PBITS) | (p + 1)
            m_tot += 1
    return out[:m_tot]


def levels_of(start, bound, g, chunk=200_000):
    """Sorted unique keys per points level, from the start keys forward."""
    w, n, wmask, order, rare = g
    start = np.unique(start)
    ps = start & PMASK
    levels = {}
    nxt = np.empty(0, np.int64)
    for p in range(int(ps.min()), bound + 1):
        cur = np.union1d(nxt, start[ps == p])
        levels[p] = cur
        parts = [np.unique(_succ(cur[i:i + chunk], bound, w, n, wmask, order, rare, 0.25))
                 for i in range(0, len(cur), chunk)]
        nxt = np.unique(np.concatenate(parts)) if parts else np.empty(0, np.int64)
    return levels


# --- P: sweep by coupon points --------------------------------------------------------------------------------------

@nb.njit(cache=True, parallel=True)
def _levelP(K, Kn, Vn, V, cmax, J, enc, dec, q, w, n, wmask, order, rare, pb):
    nW = _pop(wmask)
    nb_ = (len(K) + 4095) // 4096
    for b in nb.prange(nb_):
        nxt = np.empty(n, np.int64)
        prb = np.empty(n, np.float64)
        acc = np.empty(J + 1, np.float64)
        rows2 = np.empty(n, np.int64)
        for r in range(b * 4096, min(len(K), (b + 1) * 4096)):
            k = K[r]
            S = k >> PBITS
            p = k & PMASK
            hw = _pop(S & wmask)
            miss = nW - hw
            m = 0
            if miss > 0 and cmax > 0:
                o = _slot(S, wmask, order)
                if o >= 0:
                    m = _trans(S, p, o, w, n, rare, pb, nxt, prb)
            for i in range(m):
                rows2[i] = np.searchsorted(Kn, (nxt[i] << PBITS) | (p + 1))
            for c in range(cmax + 1):
                if c == 0 or m == 0:
                    for t in range(J):
                        acc[t] = 1.0 if miss <= t else 0.0
                    acc[J] = hw
                else:
                    for t in range(J + 1):
                        acc[t] = 0.0
                    for i in range(m):
                        for t in range(J + 1):
                            acc[t] += prb[i] * (Vn[rows2[i], c - 1, t] * dec[t])
                for t in range(J + 1):
                    x = acc[t] * enc[t]
                    if q:
                        x = np.floor(x + 0.5)
                    V[r, c, t] = x


@nb.njit(cache=True)
def _accP(hkeys, base, plan, cap, idx, K, V, dec, C, acc):
    for i in idx:
        r = np.searchsorted(K, hkeys[i])
        for B in range(max(cap[i], base[i]), C + 1):
            for t in range(acc.shape[2]):
                acc[plan[i], B, t] += V[r, B - base[i], t] * dec[t]


def sweepP(levels, hk, hb, hp, hc, nplans, C, J, q, g, nW, timing):
    w, n, wmask, order, rare = g
    enc, dec = codecs(J, nW, q)
    dt = np.uint16 if q else np.float32
    acc = np.zeros((nplans, C + 1, J + 1))
    hl = hk & PMASK
    Vn, Kn = np.zeros((0, 1, J + 1), dt), np.empty(0, np.int64)
    t0 = time.time()
    for p in sorted(levels, reverse=True):
        K = levels[p]
        cmax = C - p
        V = np.empty((len(K), cmax + 1, J + 1), dt)
        _levelP(K, Kn, Vn, V, cmax, J, enc, dec, q, w, n, wmask, order, rare, 0.25)
        idx = np.nonzero(hl == p)[0]
        if len(idx):
            _accP(hk, hb, hp, hc, idx, K, V, dec, C, acc)
        Vn, Kn = V, K
    timing["sweep"] = timing.get("sweep", 0) + time.time() - t0
    return acc


# --- L: sweep by coupons left -------------------------------------------------------------------------------------

@nb.njit(cache=True)
def _csr_count(K, bound, w, n, wmask, order, rare, pb, cnt):
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for r in range(len(K)):
        k = K[r]
        S = k >> PBITS
        p = k & PMASK
        cnt[r] = 0
        if (S & wmask) == wmask or p >= bound:
            continue
        o = _slot(S, wmask, order)
        if o >= 0:
            cnt[r] = _trans(S, p, o, w, n, rare, pb, nxt, prb)


@nb.njit(cache=True)
def _csr_fill(K, Kn, off_next, start, bound, w, n, wmask, order, rare, pb, sidx, sprb):
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for r in range(len(K)):
        k = K[r]
        S = k >> PBITS
        p = k & PMASK
        if (S & wmask) == wmask or p >= bound:
            continue
        o = _slot(S, wmask, order)
        if o < 0:
            continue
        m = _trans(S, p, o, w, n, rare, pb, nxt, prb)
        for i in range(m):
            sidx[start[r] + i] = off_next + np.searchsorted(Kn, (nxt[i] << PBITS) | (p + 1))
            sprb[start[r] + i] = prb[i]


@nb.njit(cache=True, parallel=True)
def _layerL(nrows, ptr, sidx, sprb, miss, hw, Vp, V, c, J, enc, dec, q):
    nb_ = (nrows + 4095) // 4096
    for b in nb.prange(nb_):
        acc = np.empty(J + 1, np.float64)
        for r in range(b * 4096, min(nrows, (b + 1) * 4096)):
            a, z = ptr[r], ptr[r + 1]
            if c == 0 or a == z:
                for t in range(J):
                    acc[t] = 1.0 if miss[r] <= t else 0.0
                acc[J] = hw[r]
            else:
                for t in range(J + 1):
                    acc[t] = 0.0
                for i in range(a, z):
                    for t in range(J + 1):
                        acc[t] += sprb[i] * (Vp[sidx[i], t] * dec[t])
            for t in range(J + 1):
                x = acc[t] * enc[t]
                if q:
                    x = np.floor(x + 0.5)
                V[r, t] = x


@nb.njit(cache=True)
def _accL(hrow, base, plan, cap, c, V, dec, C, acc):
    for i in range(len(hrow)):
        B = base[i] + c
        if B <= C and B >= cap[i]:
            for t in range(acc.shape[2]):
                acc[plan[i], B, t] += V[hrow[i], t] * dec[t]


def sweepL(levels, hk, hb, hp, hc, nplans, C, J, q, g, nW, timing, sizes):
    w, n, wmask, order, rare = g
    t0 = time.time()
    ps = sorted(levels)
    off = {}
    tot = 0
    for p in ps:
        off[p] = tot
        tot += len(levels[p])
    K_all = np.concatenate([levels[p] for p in ps])
    cnt = np.empty(tot, np.int64)
    _csr_count(K_all, C, w, n, wmask, order, rare, 0.25, cnt)
    ptr = np.zeros(tot + 1, np.int64)
    np.cumsum(cnt, out=ptr[1:])
    del cnt
    sidx = np.empty(ptr[-1], np.int32)
    sprb = np.empty(ptr[-1], np.float32)
    for p in ps:
        if p + 1 in levels:
            _csr_fill(levels[p], levels[p + 1], off[p + 1], ptr[off[p]:off[p] + len(levels[p])], C, w, n, wmask,
                      order, rare, 0.25, sidx, sprb)
    hwc = _hw_all(K_all, wmask)
    nW = _pop(wmask)
    miss = nW - hwc
    hrow = np.empty(len(hk), np.int64)
    hl = hk & PMASK
    for p in ps:
        idx = np.nonzero(hl == p)[0]
        hrow[idx] = off[p] + np.searchsorted(levels[p], hk[idx])
    del K_all
    sizes["succ_entries"] = int(ptr[-1])
    timing["csr"] = timing.get("csr", 0) + time.time() - t0
    t0 = time.time()
    enc, dec = codecs(J, nW, q)
    dt = np.uint16 if q else np.float32
    Vp = np.zeros((tot, J + 1), dt)
    V = np.zeros((tot, J + 1), dt)
    acc = np.zeros((nplans, C + 1, J + 1))
    for c in range(C + 1):
        nrows = sum(len(levels[p]) for p in ps if p <= C - c)   # rows with points <= C - c (a prefix)
        _layerL(nrows, ptr, sidx, sprb, miss, hwc, Vp, V, c, J, enc, dec, q)
        _accL(hrow, hb, hp, hc, c, V, dec, C, acc)
        Vp, V = V, Vp
    timing["sweep"] = timing.get("sweep", 0) + time.time() - t0
    return acc


@nb.njit(cache=True)
def _hw_all(K, wmask):
    out = np.empty(len(K), np.int64)
    for i in range(len(K)):
        out[i] = _pop((K[i] >> PBITS) & wmask)
    return out


# --- driver ---------------------------------------------------------------------------------------------------------

def main():
    case, C, variant, J, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
    hn, tr = CASES[case]
    h = H.get_horse(H.load_data(), hn)
    ev = X.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), C=1)
    ctx = ev.a
    w, n, W, M, lmask, wmask, fod, cyc, rare = ctx
    order = np.array(sorted(range(n), key=lambda i: (w[i], i)), np.int64)
    g = (w, n, wmask, order, rare)
    nW = _pop(int(wmask))
    small = case == "tiny"
    timing, sizes, res = {}, {}, {}
    table = TableR(ctx, C, J) if variant == "R" else None
    d = Dict.empty(key_type=types.int64, value_type=types.int64) if variant == "D" else None
    for bi, (plans, runs, seed) in enumerate(batches(C, small)):
        t0 = time.time()
        hk, hb, hp, hc = simulate(ctx, plans, runs, seed)
        timing["simulate"] = timing.get("simulate", 0) + time.time() - t0
        t0 = time.time()
        if variant == "none":
            continue
        if variant == "D":
            _explore(np.unique(hk), d, len(d), C, w, n, wmask, order, rare, 0.25)
            timing["states"] = timing.get("states", 0) + time.time() - t0
            sizes["states"] = len(d)
            continue
        if variant == "R":
            table.ensure(hk)
            timing["fill"] = timing.get("fill", 0) + time.time() - t0
            t0 = time.time()
            acc = np.zeros((len(plans), C + 1, J + 1))
            _accR(_rows(hk, table.d), hb, hp, hc, table.V, C, acc)
            timing["query"] = timing.get("query", 0) + time.time() - t0
            sizes["states"] = table.rows
            sizes["capacity"] = len(table.V)
        else:
            levels = levels_of(hk, C, g)
            timing["states"] = timing.get("states", 0) + time.time() - t0
            sizes[f"states_b{bi + 1}"] = int(sum(len(v) for v in levels.values()))
            sizes[f"largest_level_b{bi + 1}"] = int(max(len(v) for v in levels.values()))
            q = variant.endswith("16")
            if variant[0] == "P":
                acc = sweepP(levels, hk, hb, hp, hc, len(plans), C, J, q, g, nW, timing)
            else:
                acc = sweepL(levels, hk, hb, hp, hc, len(plans), C, J, q, g, nW, timing, sizes)
            del levels
        res[f"b{bi + 1}"] = (acc / runs).astype(np.float64)
    if res:
        np.savez_compressed(out + ".npz", **res)
    timing = {k: round(v, 2) for k, v in timing.items()}
    timing["table_total"] = round(sum(v for k, v in timing.items() if k != "simulate"), 2)
    print(json.dumps({"case": case, "C": C, "variant": variant, "J": J, "time": timing, "sizes": sizes,
                      "peak_MB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)}), flush=True)


if __name__ == "__main__":
    main()
