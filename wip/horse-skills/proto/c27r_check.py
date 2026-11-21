"""C27r check: the DP's W and A values (best desired skill) against a plain memoized recursion, on sampled states
(T8 Skilled 1, at30 horses, C = 6); and how often W's best desired differs from the rule's on the full-set goal.
Usage: python3 -I c27r_check.py"""
import functools, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(HERE))), HERE]
import numpy as np
from bdo import horses as H, horses_fast as F
import c27r

C = 6
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)")
ev = F.Evaluator(h, h.M(H.training_bonus("Skilled 1"), 0, 0), max_budget=C)
w, n, W, M = ev.args
lmask, wmask, fod, cyc, order, rare = ev.masks
S, base, pts = F._many30(300, 3, w, n, W, M, 0, 1, 0, 0, 1, lmask, wmask, fod, cyc, order, rare, 0.25, 0, 30, 0, False)
hk = (S << F.PBITS) | (np.arange(300) % 9)          # varied starting points
K = c27r.reach(hk, C, n, wmask, order)
prev, cur = np.zeros((len(K), 6)), np.zeros((len(K), 6))
for c in range(C + 1):
    c27r._layer(K, prev, cur, c, w, n, wmask, order, rare, 0.25)
    prev, cur = cur, prev
V = prev                                             # values at c = C
wl, ol, rl, wm = list(w), [int(x) for x in order], [int(x) for x in rare], int(wmask)
nW = bin(wm).count("1")


@functools.lru_cache(maxsize=None)
def f(S, p, c, v, goal):
    hw = bin(S & wm).count("1")
    term = (1.0 if hw == nW else 0.0) if goal == 0 else float(hw)
    o = next((i for i in ol if S >> i & 1 and not wm >> i & 1), -1) if hw < nW else -1
    if c == 0 or o < 0:
        return term
    free = [i for i in range(n) if not S >> i & 1 and i != o]
    rt = next(i for i in rl if i in free) if any(i in free for i in rl) else -1
    cands = [rt] if v == 0 else [t for t in free if wm >> t & 1] if v == 1 else free
    best = -1.0
    for t in cands:
        b = 1 + 0.25 * p
        tot = sum(wl[i] * (b if i == t else 1) for i in free)
        val = sum(wl[i] * (b if i == t else 1) / tot * f((S & ~(1 << o)) | (1 << i), 0 if i == t else p + 1, c - 1, v, goal)
                  for i in free)
        best = max(best, val)
    return best


rows = np.searchsorted(K, np.unique(hk))
worst = 0.0
for r in rows[:120]:
    k = int(K[r])
    for v in range(3):
        for goal in range(2):
            worst = max(worst, abs(V[r, 2 * v + goal] - f(k >> F.PBITS, k & F.PMASK, C, v, goal)))
print(f"DP vs recursion, 120 start states x 3 variants x 2 goals, c = {C}: worst diff {worst:.1e}")
d = V[:, 2] - V[:, 0]
print(f"all {len(K)} reachable states at c = {C}: full set W - R max {d.max():.2e}, states with W > R + 1e-9: "
      f"{(d > 1e-9).sum()}; A - R max {(V[:, 4] - V[:, 0]).max():.2e}")
