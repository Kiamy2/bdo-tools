import sys, os, time
sys.path[:0] = ["/home/claude/bdo-tools", os.path.dirname(os.path.abspath(__file__))]
import numpy as np
from bdo import horses as H
import table_nb as T
import c27_nb as O
d = H.load_data()
SC = [("F2 Diné A7", "Mythical Diné", 21.7, 0, 0, [("at30", 1, 0, (10, 15, 20)), ("coursier", 24, 3, (10,)),
       ("coursier_v2", 15, 9, (10,)), ("coursier_v2", 7, 13, (15,)), ("coursier_v2", 3, 17, (20,))]),
      ("F3 Doom A7", "Doom (T9)", 21.7, 0, 0, [("at30", 1, 0, (10, 15, 20)), ("coursier_v2", 14, 9, (10,))]),
      ("F1 T8 P10", "T8 example (bdolytics icon horse_71)", 16.8, 0, 0, [("at30", 1, 0, (10, 20)), ("coursier_v2", 17, 6, (10,))])]
for name, hn, tb, g, b, plans in SC:
    h = H.get_horse(d, hn)
    ev = T.Evaluator(h, h.M(tb, g, b), max_budget=40); A = ev.args
    opt = O.OptTable(list(A["w"]), int(A["wmask"]), list(A["order"]), ev.rare, C=20, pmax=20)
    print(f"== {name}", flush=True)
    for st, L, cap, budgets in plans:
        S, base, pts = T._many30(2000, 3, A["w"], A["n"], A["W"], A["M"], T.STRAT[st], L, cap, 0, 1, A["lmask"], A["wmask"], A["fod"], A["order"], A["rare"], 0.25, 0, 30)
        keys = (S << T.PBITS) | pts
        t = time.time(); opt.ensure(keys); dt = time.time() - t
        ev.table.ensure(keys)
        rows = np.array([opt.d[int(k)] for k in keys]); rr = ev.table.rows_of(keys)
        for B in budgets:
            idx = np.minimum(B - base, 20)
            g = float(opt.arr["G"][rows, idx].mean()); hh = float(opt.arr["H"][rows, idx].mean())
            gr = float(ev.table.G[rr, np.minimum(B - base, 40)].mean()); hr = float(ev.table.H[rr, np.minimum(B - base, 40)].mean())
            print(f"  {st:11} start {L:>2} spend<={cap:<2} {B:>2} coupons: full set rarest {100*gr:5.2f}% -> best {100*g:5.2f}% ({100*(g-gr):+.2f}) | travel skills rarest {hr:.3f} -> best {hh:.3f} ({hh-hr:+.3f})", flush=True)
        print(f"     (table {opt.rows} entries, +{dt:.1f}s)", flush=True)
    del opt
