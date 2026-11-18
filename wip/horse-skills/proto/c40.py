"""C40 ticket-use: when to use Mount Level Down Tickets (redo a level-up that taught nothing).

Policies (a ticket can only be used on a level-up that taught nothing):
  always        on every such level-up, from the start (what the tool does)
  from L        only on level-ups reaching level L or more
  behind d      only while the horse has fewer learned skills than the average horse of the same plan without tickets
                at that level, minus d
Measured with the general rule's plan (no Selection Coupon), exact level-30 cleanup: the full-set chance and the
average number of tickets actually used, for 2 / 5 / 10 tickets. 9 cases (Diné, Doom, T8 x Beginner 1, Skilled 1,
Artisan 7), budgets 10 / 20 / 30, 20,000 horses per policy (same horses for every policy).

Usage: python3 -I c40.py   (writes c40_results.json, prints the summary)
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
from bdo.horses_fast import _pop, _next, _mix, _swap_k, PBITS            # noqa: E402

HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAININGS = ["Beginner 1", "Skilled 1", "Artisan 7"]
BUDGETS = [10, 20, 30]
TICKETS = [2, 5, 10]
POLICIES = [("always", 0)] + [("from", L) for L in (5, 10, 15, 20, 25)] + [("behind", d) for d in (0, 0.5, 1, 2)]
MODES = {"always": 0, "from": 1, "behind": 2}
RUNS, SEED, C = 20000, 4040, 30


@nb.njit(cache=True)
def _one(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, lmask, fod, cyc, rare, pb, switch_at, mode, param,
         curve, record):
    """One horse, level 1 -> 30, as horses_fast._level30 (no Selection Coupon) with a ticket policy. record: learned
    skills before each level-up's draw (to build the 'average horse' curve). Returns (held, spent, points, used)."""
    a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
    b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
    state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
    have = lmask
    spent = 0
    t = tickets
    pts = 0
    used = 0
    latched = False
    for lvl in range(1, 30):
        cnt = _pop(have)
        record[lvl] = cnt
        allow = mode == 0 or (mode == 1 and lvl + 1 >= param) or (mode == 2 and cnt < curve[lvl] - param)
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
            if got >= 0 or t == 0 or not allow:
                break
            t -= 1
            used += 1
        if got >= 0:
            have |= np.int64(1) << got
        if lvl + 1 < swap_from or spent >= spend_cap:
            continue
        if st == 7 and _pop(have) >= switch_at:
            latched = True
        if st == 1 or (st == 7 and not latched):
            for s in fod:
                if (have >> s) & 1 and spent < spend_cap:
                    nw, have, state = _swap_k(s, have, pts, state, w, n, rare, pb, False)
                    if nw >= 0:
                        spent += 1
                        pts += 1
        elif st == 6 or st == 7:
            if cyc >= 0 and (have >> cyc) & 1 and spent < spend_cap:
                nw, have, state = _swap_k(cyc, have, pts, state, w, n, rare, pb, False)
                if nw >= 0:
                    spent += 1
                    pts += 1
    return have, spent, pts, used


@nb.njit(cache=True, parallel=True)
def _many(runs, seed, w, n, W, M, st, swap_from, spend_cap, tickets, lmask, fod, cyc, rare, pb, switch_at, mode, param,
          curve):
    S = np.empty(runs, np.int64)
    base = np.empty(runs, np.int64)
    pts = np.empty(runs, np.int64)
    used = np.empty(runs, np.int64)
    rec = np.zeros((runs, 31), np.int64)
    for r in nb.prange(runs):
        S[r], base[r], pts[r], used[r] = _one(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, lmask, fod, cyc,
                                              rare, pb, switch_at, mode, param, curve, rec[r])
    return S, base, pts, used, rec


def main():
    d = H.load_data()
    out = []
    for hn in HORSES:
        h = H.get_horse(d, hn)
        for tr in TRAININGS:
            t0 = time.time()
            ev = F.Evaluator(h, h.M(H.training_bonus(tr), 0, 0), max_budget=C)
            w, n, W, M = ev.args
            lmask, wmask, fod, cyc, order, rare = ev.masks
            row = {"horse": hn, "training": tr, "budgets": {}}
            for B in BUDGETS:
                st, lv, cap, T = H.rule_plan(B)
                code = F.CODES[st]
                zero = np.zeros(31)
                S0, b0, p0, u0, rec = _many(RUNS, SEED, w, n, W, M, code, lv, cap, 0, lmask, fod, cyc, rare, 0.25, T,
                                            0, 0, zero)
                curve = rec.mean(axis=0).astype(np.float64)
                runs_ = [("none", 0, 0, S0, b0, p0, u0)]
                for N in TICKETS:
                    for name, prm in POLICIES:
                        S, b, p, u, _ = _many(RUNS, SEED, w, n, W, M, code, lv, cap, N, lmask, fod, cyc, rare, 0.25, T,
                                              MODES[name], prm, curve)
                        runs_.append((name, prm, N, S, b, p, u))
                hk = np.concatenate([(x[3] << PBITS) | x[5] for x in runs_])
                hb = np.concatenate([x[4] for x in runs_])
                hp = np.concatenate([np.full(RUNS, i, np.int64) for i in range(len(runs_))])
                hc = np.full(len(hk), cap, np.int64)
                acc = F.cleanup_values(hk, hb, hp, hc, len(runs_), C, C, 1, False, w, n, wmask, order, rare, 0.25)
                cell = {"plan": [st, lv, cap, T], "none": float(acc[0, B, 0] / RUNS), "policies": []}
                for i, (name, prm, N, S, b, p, u) in enumerate(runs_[1:], 1):
                    cell["policies"].append({"tickets": N, "policy": name, "param": prm,
                                             "chance": float(acc[i, B, 0] / RUNS), "used": float(u.mean())})
                row["budgets"][B] = cell
            out.append(row)
            print(f"{hn[:12]:<12} {tr:<10} {time.time() - t0:.0f}s", flush=True)
    json.dump(out, open(os.path.join(HERE, "c40_results.json"), "w"), indent=1)
    summary(out)


def summary(out):
    label = lambda q: "always" if q["policy"] == "always" else f"{q['policy']} {q['param']:g}"
    print("\nGain in the full-set chance (points) and tickets used, averaged over the 9 cases x 3 budgets")
    print("tickets | policy | gain | used | gain per ticket used | worst-case gain")
    agg = {}
    for row in out:
        for B, c in row["budgets"].items():
            for q in c["policies"]:
                agg.setdefault((q["tickets"], label(q)), []).append((100 * (q["chance"] - c["none"]), q["used"]))
    for (N, lab), v in sorted(agg.items(), key=lambda kv: (kv[0][0], -np.mean([x for x, _ in kv[1]]))):
        g = np.mean([x for x, _ in v]); u = np.mean([y for _, y in v])
        print(f"{N} | {lab} | {g:+.2f} | {u:.2f} | {g / u if u else 0:+.2f} | {min(x for x, _ in v):+.2f}")


if __name__ == "__main__":
    main()
