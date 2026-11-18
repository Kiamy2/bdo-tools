"""C40b: why a Level Down Ticket used late adds a bit more by level 30 than one used early.

One ticket, used on the first level-up from level L on that teaches nothing. Measured per L: how often the redo
teaches a skill (success), the extra learned skills at level 30 (net), and give-back = success - net (skills the
later level-ups don't teach because the extra skill shrank the unlearned weight U); also the weight of the skill the
redo taught (heavier = shrinks U more). T8 example, Skilled 1, the rule's plan for 20 coupons, 200,000 horses.
"""
import sys
sys.path[:0] = ["/home/claude/bdo-tools", "."]
import numpy as np
import numba as nb
from bdo import horses as H, horses_fast as F
from bdo.horses_fast import _pop, _next, _mix, _swap_k


@nb.njit(cache=True)
def _one(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, lmask, fod, cyc, rare, pb, switch_at, from_level):
    a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
    b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
    state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
    have, spent, t, pts, latched = lmask, 0, tickets, 0, False
    used, succ, wsucc, lvl_used, u_at = 0, 0, 0.0, 0, 0.0
    for lvl in range(1, 30):
        allow = lvl + 1 >= from_level
        got = -1
        redo = False
        while True:
            su = 0.0
            for i in range(n):
                if not (have >> i) & 1:
                    su += w[i]
            k = min(M / (su + W), 1.0 / su) if su > 0 else 0.0
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
            redo = True
            lvl_used = lvl + 1
            u_at = su
        if got >= 0:
            have |= np.int64(1) << got
            if redo:
                succ += 1
                wsucc += w[got]
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
    return have, used, succ, wsucc, lvl_used, u_at


@nb.njit(cache=True, parallel=True)
def _many(runs, seed, w, n, W, M, st, swap_from, spend_cap, tickets, lmask, fod, cyc, rare, pb, switch_at, from_level):
    S = np.empty(runs, np.int64); used = np.empty(runs, np.int64); succ = np.empty(runs, np.int64)
    wsucc = np.empty(runs); lv = np.empty(runs, np.int64); ua = np.empty(runs)
    for r in nb.prange(runs):
        S[r], used[r], succ[r], wsucc[r], lv[r], ua[r] = _one(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets,
                                                               lmask, fod, cyc, rare, pb, switch_at, from_level)
    return S, used, succ, wsucc, lv, ua


h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)")
ev = F.Evaluator(h, h.M(H.training_bonus("Skilled 1"), 0, 0), max_budget=20)
w, n, W, M = ev.args
lmask, wmask, fod, cyc, order, rare = ev.masks
st, lv, cap, T = H.rule_plan(20)
N = 200000
args = (w, n, W, M, F.CODES[st], lv, cap)
base = _many(N, 11, *args, 0, lmask, fod, cyc, rare, 0.25, T, 99)
cnt0 = F._popcounts(base[0]).mean()
print(f"T8 Skilled 1, rule plan for 20 coupons; W {W:.1f}, M {M:.3f}; skills at 30 without tickets: {cnt0:.2f}")
print("ticket from level | used at level (avg) | U then (avg) | redo teaches | weight of that skill (avg) | net extra skills at 30 | give-back")
for L in (2, 5, 10, 15, 20, 25, 28):
    S, used, succ, ws, lvu, ua = _many(N, 11, *args, 1, lmask, fod, cyc, rare, 0.25, T, L)
    u = used == 1
    s_rate = succ[u].mean()
    net = (F._popcounts(S).mean() - cnt0) / used.mean()
    print(f"{L:2} | {lvu[u].mean():5.1f} | {ua[u].mean():5.1f} | {100 * s_rate:5.1f}% | {ws[u & (succ == 1)].mean():5.2f} | "
          f"{net:+.3f} | {s_rate - net:.3f} ({100 * (s_rate - net) / s_rate:.0f}% of the redo's gain)")
