"""K2: number of reachable cleanup states per wanted-skill group (T8 Skilled 1, coursier_switch grid, 1000 horses
per plan), and time / most values held / peak RSS of cleanup_values. Run: python3 -I wip/horse-skills/proto/k2_states.py 40"""
import sys, time, numpy as np
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)")
C = int(sys.argv[1])
ev = F.Evaluator(h, h.M(H.training_bonus("Skilled 1"), 0, 0), max_budget=C)
w, n, W, M = ev.args; lmask, wmask, fod, cyc, order, rare = ev.masks
hk, hb = [], []
plans = [("coursier_switch", lv, cap, T) for lv in range(2, 30, 3) for cap in H.PLAN_CAPS if cap <= C for T in H.SWITCH_TS[::2]]
for st, lv, cap, T in plans:
    S, b, p = F._many30(1000, 1, w, n, W, M, 7, lv, cap, 0, 1, lmask, wmask, fod, cyc, order, rare, 0.25, 0, 30, T, False)
    hk.append((S << F.PBITS) | p); hb.append(b)
hk, hb = np.concatenate(hk), np.concatenate(hb)
t = time.time()
keys, cm = F._reach(hk, hb, C, w, n, wmask, order, rare, 0.25)
t1 = time.time() - t
g = F._popcounts((keys >> F.PBITS) & wmask); p = keys & F.PMASK
print(f"C={C} horses {len(hk)} states {len(keys)} reach {t1:.1f}s values {int((cm.astype(np.int64)+1).sum())}")
for gg in np.unique(g):
    s = g == gg
    print(f" g={gg}: states {s.sum():9d} values {int((cm[s].astype(np.int64)+1).sum()):11d}  p-levels {len(np.unique(p[s]))}"
          f" largest level values {max(int((cm[s & (p == q)].astype(np.int64)+1).sum()) for q in np.unique(p[s])):10d}")
import resource
for J in (1, 5):
    st = {}
    t = time.time()
    F.cleanup_values(hk, hb, np.zeros(len(hk), np.int64), hb.copy(), 1, C, J, False, w, n, wmask, order, rare, 0.25, 0, st)
    print(f"J={J}: {time.time()-t:.1f}s states {st['states']} peak values {st['peak_values']/1e6:.1f}M = {st['peak_values']*4/2**20:.0f} MB, maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f} MB")
