"""K2 early checks of the reset-aware exact cleanup sweep (bdo.horses_fast.cleanup_values).
1. exact: against a plain memoized recursion of the same model (points back to 0 on a desired hit), per horse
   and budget, for sampled end-of-leveling states (sel 0 and 1, tails).
2. pb0: with point_bonus 0 the reset changes nothing, so plans() must equal the no-reset engine (commit e7de4a0).
Run from the repo root: python3 -I wip/horse-skills/proto/k2_check.py"""
import functools, importlib.util, subprocess, sys, tempfile, os
import numpy as np
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

PB = F.PBITS


def exact_values(ev, hk, C, J, sel, pb=0.25):
    w, n, W, M = ev.args
    lmask, wmask, fod, cyc, order, rare = ev.masks
    w, order, rare, wmask = list(w), list(order), list(rare), int(wmask)
    nW = bin(wmask).count("1")

    def target(free, keep):
        first = -1
        for i in rare:
            if free >> i & 1:
                if not keep:
                    return i
                if first < 0:
                    first = i
                else:
                    return i
        return first

    @functools.lru_cache(maxsize=None)
    def f(S, p, c):
        hw = bin(S & wmask).count("1")
        miss = nW - hw
        term = tuple([1.0 if miss <= t else 0.0 for t in range(J)] + [float(hw)])
        if c == 0 or miss <= sel:
            return term
        o = next((i for i in order if S >> i & 1 and not wmask >> i & 1), -1)
        if o < 0:
            return term
        free = ~S & ~(1 << o) & ((1 << n) - 1)
        tg = target(free, sel > 0)
        ws = {i: w[i] * (1 + pb * p) if i == tg else w[i] for i in range(n) if free >> i & 1}
        if not ws:
            return term
        tot = sum(ws.values())
        acc = [0.0] * (J + 1)
        for i, x in ws.items():
            v = f((S & ~(1 << o)) | (1 << i), 0 if i == tg else p + 1, c - 1)
            for t in range(J + 1):
                acc[t] += x / tot * v[t]
        return tuple(acc)
    return [f(int(k) >> PB, int(k) & ((1 << PB) - 1), C) for k in hk], f


def check_exact():
    data = H.load_data()
    worst = 0.0
    for name, train, plan in (("T8 example (bdolytics icon horse_71)", "Skilled 1", ("coursier_switch", 10, 8, 12)),
                              ("Mythical Diné", "Artisan 7", ("coursier", 12, 6, 0)),
                              ("Doom (T9)", "Artisan 8", ("coursier_v2", 15, 4, 0))):
        h = H.get_horse(data, name)
        M = h.M(H.training_bonus(train) if hasattr(H, "training_bonus") else 0, 0, 0)
        for sel in (0, 1):
            C = 10
            ev = F.Evaluator(h, M, max_budget=C)
            w, n, W, Mx = ev.args
            lmask, wmask, fod, cyc, order, rare = ev.masks
            st, lv, cap, T = plan
            S, base, pts = F._many30(40, 5, w, n, W, Mx, F.CODES[st], lv, cap, 0, 1, lmask, wmask, fod, cyc, order,
                                     rare, 0.25, 0, 30, T, sel > 0)
            hk = (S << PB) | pts
            J = 5
            nh = len(hk)
            acc = F.cleanup_values(hk, base, np.arange(nh), base.copy(), nh, C, J, False, w, n, wmask, order, rare,
                                   0.25, sel)
            _, f = exact_values(ev, hk, C, J, sel)
            for i in range(nh):
                for B in range(int(base[i]), C + 1):
                    ex = f(int(hk[i]) >> PB, int(hk[i]) & ((1 << PB) - 1), B - int(base[i]))
                    d = np.abs(acc[i, B] - np.array(ex)).max()
                    worst = max(worst, d)
            print(f"exact {name[:12]:12s} sel={sel}: points at end of leveling {sorted(set(pts.tolist()))}, "
                  f"worst diff so far {worst:.2e}")
    return worst


def check_pb0():
    old = tempfile.mkdtemp()
    os.makedirs(f"{old}/bdo")
    os.symlink(os.path.abspath("data"), f"{old}/data")
    names = subprocess.run(["git", "ls-tree", "--name-only", "e7de4a0", "bdo/"], capture_output=True, text=True,
                           check=True).stdout.split()
    for f in (x.split("/")[-1] for x in names if x.endswith(".py")):
        src = subprocess.run(["git", "show", f"e7de4a0:bdo/{f}"], capture_output=True, text=True, check=True).stdout
        open(f"{old}/bdo/{f}", "w").write(src)
    code = f"""
import sys, json
sys.path.insert(0, {old!r})
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)")
ev = F.Evaluator(h, h.M(0, 0, 0), max_budget=20, point_bonus=0.0)
P = [("coursier_switch", 10, 12, 12), ("coursier", 14, 20, 0), ("at30", 1, 0, 0)]
r = ev.plans(P, runs=3000, seed=4, tails=True)
r2 = ev.plans(P, runs=3000, seed=4, coupon="fallback")
print(json.dumps([[r[p]["full"], r[p]["wanted"], r[p]["tails"], r2[p]["full"]] for p in P]))
"""
    import json
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=".")
    if res.returncode:
        sys.exit(res.stderr)
    o = json.loads(res.stdout)
    h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)")
    ev = F.Evaluator(h, h.M(0, 0, 0), max_budget=20, point_bonus=0.0)
    P = [("coursier_switch", 10, 12, 12), ("coursier", 14, 20, 0), ("at30", 1, 0, 0)]
    r = ev.plans(P, runs=3000, seed=4, tails=True)
    r2 = ev.plans(P, runs=3000, seed=4, coupon="fallback")
    n = [[r[p]["full"], r[p]["wanted"], r[p]["tails"], r2[p]["full"]] for p in P]
    flat = lambda x: [v for v in (np.array(x, dtype=object).ravel()) for v in (np.ravel(v) if v is not None else [])]
    worst = 0.0
    for a, b in zip(o, n):
        for x, y in zip(a, b):
            for u, v in zip(x, y):
                if u is None or v is None:
                    assert u is None and v is None
                    continue
                worst = max(worst, float(np.abs(np.array(u) - np.array(v)).max()))
    print(f"pb0: worst diff against the no-reset engine {worst:.2e}")
    return worst


if __name__ == "__main__":
    e = check_exact()
    z = check_pb0()
    print("RESULT exact", "OK" if e < 1e-5 else "DIFF", "pb0", "OK" if z < 1e-5 else "DIFF")
