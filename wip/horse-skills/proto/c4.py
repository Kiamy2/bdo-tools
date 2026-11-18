"""C4 ranges: how bad are the bad outcomes, and do near-equal plans differ in them?

For each case, budget and plan: the full-set chance, the chance of missing at most 1..4 of the learnable travel
skills at the end (after the level-30 cleanup), and the average number missing. The level-30 cleanup is scored
exactly (table over held skills and coupon points, like c36_fast.TableG, storing the tail chances and the mean).

Compared per case and budget (stage 1: 1000 horses per plan, common random numbers; then the chosen plans rerun
with 4000 fresh horses):
  rule   the current rule's plan (C37 / C37b 'any plan')
  full   best full-set chance
  safe1  best chance of missing at most 1 skill, among plans within 1 point of the best full-set chance
  safe2  same, missing at most 2
  mean   fewest skills missing on average (any plan)
Saves c4_cases/<i>.json (resumable). Summary: c4_summary.py.

Usage: python3 -I c4.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["/home/claude/bdo-tools", HERE]
import numpy as np                                                       # noqa: E402
import numba as nb                                                       # noqa: E402
from numba import types                                                  # noqa: E402
from numba.typed import Dict                                             # noqa: E402
from bdo import horses as H                                              # noqa: E402
from bdo.horses_fast import _pop, _slot, _trans, _explore, PBITS         # noqa: E402
import c36_fast as X                                                     # noqa: E402

C = 30
J = 5                                    # tails: missing <= 0, 1, 2, 3, 4
BUDGETS = [10, 15, 20, 25, 30]
OUT = os.path.join(HERE, "c4_cases")
CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30]
TS = list(range(9, 17))
PLANS = ([(0, 1, 0, 0, 0)] + [(st, s, c, 0, 0) for st in (1, 6) for s in range(2, 30) for c in CAPS]
         + [(12, s, c, 0, T) for s in range(2, 30) for c in CAPS for T in TS])
HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAININGS = ["Beginner 1", "Skilled 1", "Artisan 7", "Guru 20"]
RUNS1, RUNS2, SEED1, SEED2 = 1000, 4000, 4001, 4002
ROWS = 3_600_000                        # ~2.7 GB; Doom at Skilled 1 needs ~2.5 million


def rule_plan(B):
    b = json.load(open(os.path.join(HERE, "c37b_rules.json")))
    a = json.load(open(os.path.join(HERE, "c37_rules.json")))
    r = b.get(str(B)) or a[str(B)]
    return tuple(r["any plan"]["plan"])


@nb.njit(cache=True)
def _fillT(keys, d, T, Hm, C, J, w, n, wmask, order, rare, pb):
    nW = _pop(wmask)
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for k in keys:
        r = d[k]
        S = k >> PBITS
        p = k & ((1 << PBITS) - 1)
        miss = nW - _pop(S & wmask)
        m = 0
        if miss > 0:
            out = _slot(S, wmask, order)
            if out >= 0:
                m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
        for c in range(C + 1):
            if c == 0 or m == 0:
                for j in range(J):
                    T[r, c, j] = 1.0 if miss <= j else 0.0
                Hm[r, c] = miss
                continue
            hm = 0.0
            for j in range(J):
                T[r, c, j] = 0.0
            for i in range(m):
                k2 = (nxt[i] << PBITS) | (p + 1)
                if k2 in d:
                    r2 = d[k2]
                    for j in range(J):
                        T[r, c, j] += prb[i] * T[r2, c - 1, j]
                    hm += prb[i] * Hm[r2, c - 1]
            Hm[r, c] = hm


class TableT:
    """Exact cleanup table: tail chances T[row, coupons, j] = P(missing <= j) and mean missing Hm[row, coupons]."""

    def __init__(self, w, wmask, order, rare, C, pb=0.25):
        self.w = np.array(w, np.float64)
        self.n, self.wmask, self.C, self.pmax, self.pb = len(w), int(wmask), C, C, pb
        self.order = np.array(order, np.int64)
        self.rare = np.array(rare, np.int64)
        self.d = Dict.empty(key_type=types.int64, value_type=types.int64)
        self.rows = 0
        # allocated once at full size: growing in steps briefly needs two copies (memory peak)
        self.T = np.zeros((ROWS, C + 1, J), np.float32)
        self.Hm = np.zeros((ROWS, C + 1), np.float32)
        self.known = set()

    def ensure(self, keys):
        todo = [k for k in np.unique(keys).tolist() if k not in self.known]
        if not todo:
            return
        new = _explore(np.array(todo, np.int64), self.d, self.rows, self.pmax, self.w, self.n, self.wmask, self.order,
                       self.rare, self.pb)
        self.known.update(new.tolist())
        if not len(new):
            return
        need = self.rows + len(new)
        if need > len(self.T):
            size = max(need, int(1.5 * len(self.T)))
            T = np.zeros((size, self.C + 1, J), np.float32)
            T[:self.rows] = self.T[:self.rows]
            Hm = np.zeros((size, self.C + 1), np.float32)
            Hm[:self.rows] = self.Hm[:self.rows]
            self.T, self.Hm = T, Hm
        self.rows = need
        new = new[np.argsort(-(new & ((1 << PBITS) - 1)), kind="stable")]
        _fillT(new, self.d, self.T, self.Hm, self.C, J, self.w, self.n, self.wmask, self.order, self.rare, self.pb)


class EvalT:
    def __init__(self, horse, M, table=None):
        self.base = X.Evaluator(horse, M, C=1)           # only for the setup arrays
        w, n, W, M_, lmask, wmask, fod, cyc, rare = self.base.a
        order = sorted(range(n), key=lambda i: (w[i], i))
        self.table = table or TableT(list(w), int(wmask), order, list(rare), C)

    def plan(self, st, swap_from, cap, xa=0, xb=0, runs=1000, seed=1):
        """Array (C+1, J+1): per budget, P(missing <= j) for j < J, then the mean missing; NaN below the cap."""
        w, n, W, M, lmask, wmask, fod, cyc, rare = self.base.a
        S, base, pts = X._many30x(runs, seed, w, n, W, M, st, swap_from, cap if st else 0, xa, xb, lmask, wmask, fod,
                                  cyc, rare, 0.25, 30, 1, 0)
        keys = (S << PBITS) | pts
        self.table.ensure(keys)
        rows = X._rows(keys, self.table.d)
        out = np.full((C + 1, J + 1), np.nan)
        for B in range(cap if st else 0, C + 1):
            left = B - base
            out[B, :J] = self.table.T[rows, left].mean(axis=0)
            out[B, J] = self.table.Hm[rows, left].mean()
        return out


def main():
    os.makedirs(OUT, exist_ok=True)
    d = H.load_data()
    i = 0
    for hn in HORSES:
        h = H.get_horse(d, hn)
        table = ev = None                # free the previous horse's table first
        for tr in TRAININGS:
            f = os.path.join(OUT, f"{i}.json")
            i += 1
            if os.path.exists(f):
                continue
            t = time.time()
            M = h.M(H.training_bonus(tr), 0, 0)
            ev = EvalT(h, M, table)
            table = ev.table
            V = np.array([ev.plan(*p, runs=RUNS1, seed=SEED1) for p in PLANS])       # (plans, C+1, J+1)
            res = {"horse": hn, "training": tr, "budgets": {}}
            for B in BUDGETS:
                v = V[:, B]
                ok = ~np.isnan(v[:, 0])
                full = np.where(ok, v[:, 0], -1)
                near = ok & (full >= full.max() - 0.01)
                pick = {"full": int(np.argmax(full)),
                        "safe1": int(np.argmax(np.where(near, v[:, 1], -1))),
                        "safe2": int(np.argmax(np.where(near, v[:, 2], -1))),
                        "mean": int(np.argmax(np.where(ok, -v[:, J], -99)))}
                chosen = {"rule": rule_plan(B), **{k: PLANS[j] for k, j in pick.items()}}
                res["budgets"][B] = {k: {"plan": list(map(int, p)),
                                         "stage1": [round(float(x), 5) for x in ev.plan(*p, runs=RUNS1, seed=SEED1)[B]],
                                         "check": [round(float(x), 5) for x in ev.plan(*p, runs=RUNS2, seed=SEED2)[B]]}
                                     for k, p in chosen.items()}
            res["secs"] = round(time.time() - t)
            res["table_rows"] = table.rows
            json.dump(res, open(f, "w"), indent=1)
            print(f"{i}/{len(HORSES) * len(TRAININGS)} {hn} {tr}: {res['secs']}s, table {table.rows} rows", flush=True)


if __name__ == "__main__":
    main()
