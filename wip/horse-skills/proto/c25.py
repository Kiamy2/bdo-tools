"""C25 Selection Coupon: what one Mount Skill Selection Coupon is worth, and how to use it.

The coupon changes one current skill into a chosen one (once per horse; Skill Change Points kept). Used at the very
end, it turns "missing exactly 1 wanted skill" into the full set, if the horse holds an unwanted skill to change
(it does whenever it has at least as many learned skills as there are wanted ones). Compared per case and budget,
with the general rule's plan (bdo.horses.rule_plan) for the leveling:
  none    no Selection Coupon (full set after the usual cleanup)
  end     used at the end; the cleanup as usual (targets the rarest missing skill)
  end2    used at the end; the cleanup keeps the rarest missing skill for it and targets the next rarest
  early   used at level 30 before the cleanup, on the rarest missing skill (then the usual cleanup)
Worth: change coupons the 'none' plan needs to match each option (rule plans at higher budgets).
Exact level-30 values (points sweep, as in bdo/horses_fast.py); 20,000 horses per plan.

Usage: python3 -I c25.py   (writes c25_results.json and prints the summary)
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
from bdo.horses_fast import _pop, _slot, PBITS                           # noqa: E402

PM = (1 << PBITS) - 1
HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAININGS = ["Beginner 1", "Skilled 1", "Artisan 7", "Guru 20"]
BUDGETS = [10, 15, 20, 25, 30]
CMAX = 50
RUNS, SEED = 20000, 2511


@nb.njit(cache=True)
def _trans2(S, p, out, w, n, wmask, rare, pb, nxt, prb, keep_rarest):
    """Like horses_fast._trans; with keep_rarest, the desired skill is the second rarest missing wanted skill when
    two or more are missing (the rarest is left for the Selection Coupon)."""
    full = (np.int64(1) << n) - 1
    free = ~S & ~(np.int64(1) << out) & full
    target, seen = -1, 0
    for i in rare:
        if (free >> i) & 1:
            seen += 1
            target = i
            if not keep_rarest or seen == 2:
                break
    if keep_rarest and seen < 2:
        for i in rare:                            # fewer than two missing: the rarest missing one
            if (free >> i) & 1:
                target = i
                break
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
def _succ2(keys, bound, w, n, wmask, order, rare, pb, keep_rarest):
    out = np.empty(len(keys) * n, np.int64)
    m_tot = 0
    nxt = np.empty(n, np.int64)
    prb = np.empty(n, np.float64)
    for k in keys:
        S = k >> PBITS
        p = k & PM
        if (S & wmask) == wmask or p >= bound:
            continue
        o = _slot(S, wmask, order)
        if o < 0:
            continue
        m = _trans2(S, p, o, w, n, wmask, rare, pb, nxt, prb, keep_rarest)
        for i in range(m):
            out[m_tot] = (nxt[i] << PBITS) | (p + 1)
            m_tot += 1
    return out[:m_tot]


@nb.njit(cache=True, parallel=True)
def _level2(K, Kn, Vn, V, cmax, w, n, wmask, order, rare, pb, keep_rarest):
    """V[row, c] = P(missing <= 1 after the cleanup with c coupons left), cleanup targeting per keep_rarest."""
    nW = _pop(wmask)
    for b in nb.prange((len(K) + 4095) // 4096):
        nxt = np.empty(n, np.int64)
        prb = np.empty(n, np.float64)
        rows2 = np.empty(n, np.int64)
        for r in range(b * 4096, min(len(K), (b + 1) * 4096)):
            k = K[r]
            S = k >> PBITS
            p = k & PM
            miss = nW - _pop(S & wmask)
            m = 0
            if miss > 1 and cmax > 0:              # at most 1 missing: done (the coupon finishes it)
                o = _slot(S, wmask, order)
                if o >= 0:
                    m = _trans2(S, p, o, w, n, wmask, rare, pb, nxt, prb, keep_rarest)
            for i in range(m):
                rows2[i] = np.searchsorted(Kn, (nxt[i] << PBITS) | (p + 1))
            for c in range(cmax + 1):
                if c == 0 or m == 0:
                    V[r, c] = 1.0 if miss <= 1 else 0.0
                else:
                    x = 0.0
                    for i in range(m):
                        x += prb[i] * Vn[rows2[i], c - 1]
                    V[r, c] = x


def levels2(start, bound, g, keep_rarest):
    w, n, wmask, order, rare = g
    start = np.unique(start)
    ps = start & PM
    levels, nxt = {}, np.empty(0, np.int64)
    for p in range(int(ps.min()), bound + 1):
        cur = np.union1d(nxt, start[ps == p])
        levels[p] = cur
        parts = [np.unique(_succ2(cur[i:i + 200_000], bound, w, n, wmask, order, rare, 0.25, keep_rarest))
                 for i in range(0, len(cur), 200_000)]
        nxt = np.unique(np.concatenate(parts)) if parts else np.empty(0, np.int64)
    return levels


def le1_values(hk, hb, hp, hc, nplans, C, g, keep_rarest):
    """acc[plan, B] = sum over the plan's horses of P(missing <= 1 after the cleanup) with B - base coupons."""
    w, n, wmask, order, rare = g
    acc = np.zeros((nplans, C + 1, 1))
    levels = levels2(hk, C, g, keep_rarest)
    hl = hk & PM
    Kn, Vn = np.empty(0, np.int64), np.zeros((0, 1))
    one = np.ones(1)
    for p in sorted(levels, reverse=True):
        K = levels.pop(p)
        V = np.empty((len(K), C - p + 1))
        _level2(K, Kn, Vn, V, C - p, w, n, wmask, order, rare, 0.25, keep_rarest)
        idx = np.nonzero(hl == p)[0]
        if len(idx):
            F._accumulate(hk, hb, hp, hc, idx, K, V[:, :, None], one, C, acc)
        Kn, Vn = K, V
    return acc[:, :, 0]


@nb.njit(cache=True)
def _early(hk, wmask, order, rare):
    """Selection Coupon at level 30 before the cleanup: rarest unwanted held -> rarest missing wanted skill."""
    out = hk.copy()
    for i in range(len(hk)):
        S = hk[i] >> PBITS
        if (S & wmask) == wmask:
            continue
        o = _slot(S, wmask, order)
        if o < 0:
            continue
        for j in rare:
            if not (S >> j) & 1:
                out[i] = (((S & ~(np.int64(1) << o)) | (np.int64(1) << j)) << PBITS) | (hk[i] & PM)
                break
    return out


def main():
    d = H.load_data()
    plans = sorted({H.rule_plan(B) for B in range(0, CMAX + 1)})
    pidx = {p: i for i, p in enumerate(plans)}
    out = []
    for hn in HORSES:
        h = H.get_horse(d, hn)
        for tr in TRAININGS:
            t0 = time.time()
            ev = F.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), max_budget=CMAX)
            w, n, W, M = ev.args
            lmask, wmask, fod, cyc, order, rare = ev.masks
            g = (w, n, wmask, order, rare)
            nW = _pop(int(wmask))
            hk, hb, hp, hc = [], [], [], []
            for i, (st, lv, cap, T) in enumerate(plans):
                S, b, pts = F._many30(RUNS, SEED, w, n, W, M, F.CODES[st], lv, cap, 0, 1, lmask, wmask, fod, cyc,
                                      order, rare, 0.25, 0, 30, T)
                hk.append((S << PBITS) | pts)
                hb.append(b)
                hp.append(np.full(RUNS, i, np.int64))
                hc.append(np.full(RUNS, cap, np.int64))
            hk, hb, hp, hc = map(np.concatenate, (hk, hb, hp, hc))
            spare = F._popcounts(hk >> PBITS) >= nW            # enough skills to have one to change
            res = {}
            res["none"] = F.cleanup_values(hk, hb, hp, hc, len(plans), CMAX, CMAX, 1, False, *g, 0.25)[:, :, 0]
            res["early"] = F.cleanup_values(np.where(spare, _early(hk, wmask, order, rare), hk), hb, hp, hc,
                                            len(plans), CMAX, CMAX, 1, False, *g, 0.25)[:, :, 0]
            hp_sp = np.where(spare, hp, len(plans))             # horses without a spare skill: dummy plan
            for name, kr in (("end", False), ("end2", True)):
                a = le1_values(hk, hb, hp_sp, hc, len(plans) + 1, CMAX, g, kr)[:len(plans)]
                no_sp = F.cleanup_values(hk[~spare], hb[~spare], hp[~spare], hc[~spare], len(plans), CMAX, CMAX, 1,
                                         False, *g, 0.25)[:, :, 0] if (~spare).any() else 0
                res[name] = a + no_sp                           # no spare skill: only the full set counts
            curve = {k: [v[pidx[H.rule_plan(B)], B] / RUNS for B in range(CMAX + 1)] for k, v in res.items()}
            row = {"horse": hn, "training": tr, "no_spare_share": float(1 - spare.mean()), "budgets": {}}
            for B in BUDGETS:
                cell = {k: curve[k][B] for k in res}
                for k in ("end", "end2", "early"):
                    need = next((B2 for B2 in range(B, CMAX + 1) if curve["none"][B2] >= curve[k][B] - 1e-12), None)
                    cell[f"worth_{k}"] = None if need is None else need - B
                row["budgets"][B] = cell
            out.append(row)
            print(f"{hn[:12]:<12} {tr:<10} done in {time.time() - t0:.0f}s", flush=True)
    json.dump(out, open(os.path.join(HERE, "c25_results.json"), "w"), indent=1)
    print("\ncase | budget | none | end | end2 | early | worth in change coupons: end / end2 / early")
    for row in out:
        for B, c in row["budgets"].items():
            wo = lambda k: ">" + str(CMAX - B) if c[f"worth_{k}"] is None else str(c[f"worth_{k}"])
            print(f"{row['horse'].split(' (')[0][:10]} {row['training']:<10} | {B} | {100 * c['none']:.1f} | "
                  f"{100 * c['end']:.1f} | {100 * c['end2']:.1f} | {100 * c['early']:.1f} | "
                  f"{wo('end')} / {wo('end2')} / {wo('early')}")


if __name__ == "__main__":
    main()
