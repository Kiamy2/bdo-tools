"""Fast engine for horse_skills (optional: needs numba, see requirements-optional.txt).

Same model and plan rules as bdo.horses.simulate_plan, with two differences:
- the leveling is compiled with numba (about 30x faster per core, all cores used);
- the level-30 cleanup is not simulated but computed exactly: a table gives, for every held-skill set and number
  of Skill Change Points, the chance of ending with every wanted skill (and the expected number of wanted skills)
  with c coupons left, under the same cleanup rule (swap the rarest unwanted skill held, desired = rarest missing
  wanted skill). Same averages as simulating it, with much less noise.
The table depends only on the horse's weights, the wanted set and the point bonus, so one table serves every plan.

Random numbers differ from bdo.horses (each simulated horse has its own generator, so results don't depend on the
number of cores): results agree statistically, not number for number.
"""
import numpy as np

try:
    import numba as nb
    from numba import types
    from numba.typed import Dict
except ImportError:                                                       # pragma: no cover
    nb = None

from . import horses as H


def available():
    return nb is not None


if nb is not None:
    PBITS = 7                                    # Skill Change Points stored in the low 7 bits of a table key

    @nb.njit(cache=True, inline="always")
    def _next(state):
        """splitmix64 step: (new state, float in [0, 1))"""
        state = state + np.uint64(0x9E3779B97F4A7C15)
        z = state
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
        return state, float(z >> np.uint64(11)) * (1.0 / 9007199254740992.0)

    @nb.njit(cache=True, inline="always")
    def _mix(z):
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return z ^ (z >> np.uint64(31))

    @nb.njit(cache=True, inline="always")
    def _pop(x):
        c = 0
        while x:
            x &= x - 1
            c += 1
        return c

    @nb.njit(cache=True)
    def _swap(out, have, pts, state, w, n, rare, pb):
        """Coupon: replace skill 'out' by a draw among unlearned skills (not 'out'); desired = rarest missing
        wanted skill, weight x (1 + pb * points). Returns (new skill or -1, have, state)."""
        free = ~have & ~(np.int64(1) << out)
        target = -1
        for i in rare:
            if (free >> i) & 1:
                target = i
                break
        boost = 1.0 + pb * pts
        tot = 0.0
        for i in range(n):
            if (free >> i) & 1:
                tot += w[i] * boost if i == target else w[i]
        if tot == 0.0:
            return -1, have, state
        state, r = _next(state)
        x = r * tot
        new = -1
        for i in range(n):
            if (free >> i) & 1:
                new = i
                x -= w[i] * boost if i == target else w[i]
                if x < 0:
                    break
        have = (have & ~(np.int64(1) << out)) | (np.int64(1) << new)
        return new, have, state

    @nb.njit(cache=True)
    def _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod, cyc, order,
                 rare, pb, points, max_level):
        """One horse from start_level to max_level, without the level-30 cleanup.
        st: 0 at30, 1 coursier, 2 once, 3 hard, 4 natural, 6 coursier_v2 (cycles skill 'cyc').
        Returns (held skills, coupons spent while leveling, Skill Change Points)."""
        a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
        b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
        state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
        have = lmask
        spent = 0
        t = tickets
        pts = points
        for lvl in range(start_level, max_level):
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
                if got >= 0 or t == 0:
                    break
                t -= 1
            if got >= 0:
                have |= np.int64(1) << got
            if lvl + 1 < swap_from or spent >= spend_cap:
                continue
            if st == 1:
                for s in fod:
                    if (have >> s) & 1 and spent < spend_cap:
                        nw, have, state = _swap(s, have, pts, state, w, n, rare, pb)
                        if nw >= 0:
                            spent += 1
                            pts += 1
            elif st == 6:
                if cyc >= 0 and (have >> cyc) & 1 and spent < spend_cap:
                    nw, have, state = _swap(cyc, have, pts, state, w, n, rare, pb)
                    if nw >= 0:
                        spent += 1
                        pts += 1
            elif st == 2:
                if lvl + 1 == swap_from and swap_from > 1:
                    todo = np.empty(n, np.int64)
                    m = 0
                    for s in order:
                        if (have >> s) & 1 and not (wmask >> s) & 1:
                            todo[m] = s
                            m += 1
                    for q in range(m):
                        s = todo[q]
                        if (have >> s) & 1 and not (wmask >> s) & 1 and spent < spend_cap:
                            nw, have, state = _swap(s, have, pts, state, w, n, rare, pb)
                            if nw >= 0:
                                spent += 1
                                pts += 1
                elif got >= 0 and not (wmask >> got) & 1 and (have >> got) & 1 and spent < spend_cap:
                    nw, have, state = _swap(got, have, pts, state, w, n, rare, pb)
                    if nw >= 0:
                        spent += 1
                        pts += 1
            elif st == 3:
                todo = np.empty(n, np.int64)
                m = 0
                for s in order:
                    if (have >> s) & 1 and not (wmask >> s) & 1:
                        todo[m] = s
                        m += 1
                for q in range(m):
                    slot = todo[q]
                    while slot >= 0 and not (wmask >> slot) & 1 and (have >> slot) & 1 and spent < spend_cap:
                        slot, have, state = _swap(slot, have, pts, state, w, n, rare, pb)
                        if slot >= 0:
                            spent += 1
                            pts += 1
        return have, spent, pts

    @nb.njit(cache=True, parallel=True)
    def _many30(runs, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod, cyc,
                order, rare, pb, points, max_level):
        S = np.empty(runs, np.int64)
        base = np.empty(runs, np.int64)
        pts = np.empty(runs, np.int64)
        for r in nb.prange(runs):
            a, b, c = _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask,
                               fod, cyc, order, rare, pb, points, max_level)
            S[r] = a
            base[r] = b
            pts[r] = c
        return S, base, pts

    # --- exact level-30 cleanup table ----------------------------------------------------------------------------

    @nb.njit(cache=True)
    def _slot(S, wmask, order):
        for i in order:
            if (S >> i) & 1 and not (wmask >> i) & 1:
                return i
        return -1

    @nb.njit(cache=True)
    def _trans(S, p, out, w, n, rare, pb, nxt, prb):
        full = (np.int64(1) << n) - 1
        free = ~S & ~(np.int64(1) << out) & full
        target = -1
        for i in rare:
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
    def _explore(starts, d, n_rows, pmax, w, n, wmask, order, rare, pb):
        new = []
        stack = [np.int64(0)] * 0
        for k in starts:
            stack.append(k)
        nxt = np.empty(n, np.int64)
        prb = np.empty(n, np.float64)
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
            out = _slot(S, wmask, order)
            if out < 0:
                continue
            m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
            for j in range(m):
                k2 = (nxt[j] << PBITS) | (p + 1)
                if k2 not in d:
                    stack.append(k2)
        res = np.empty(len(new), np.int64)
        for i in range(len(new)):
            res[i] = new[i]
        return res

    @nb.njit(cache=True)
    def _fill(keys, d, G, Hh, C, w, n, wmask, order, rare, pb):
        nW = _pop(wmask)
        nxt = np.empty(n, np.int64)
        prb = np.empty(n, np.float64)
        for k in keys:
            r = d[k]
            S = k >> PBITS
            p = k & ((1 << PBITS) - 1)
            hw = _pop(S & wmask)
            if hw == nW:
                for c in range(C + 1):
                    G[r, c] = 1.0
                    Hh[r, c] = nW
                continue
            G[r, 0] = 0.0
            Hh[r, 0] = hw
            out = _slot(S, wmask, order)
            m = 0
            if out >= 0:
                m = _trans(S, p, out, w, n, rare, pb, nxt, prb)
            for c in range(1, C + 1):
                g = 0.0
                h = 0.0
                if m == 0:
                    h = hw
                for j in range(m):
                    k2 = (nxt[j] << PBITS) | (p + 1)
                    if k2 in d:
                        r2 = d[k2]
                        g += prb[j] * G[r2, c - 1]
                        h += prb[j] * Hh[r2, c - 1]
                    else:                      # beyond pmax: only reached when no coupon is left anyway
                        h += prb[j] * _pop(nxt[j] & wmask)
                G[r, c] = g
                Hh[r, c] = h

    @nb.njit(cache=True)
    def _rows(keys, d):
        out = np.empty(len(keys), np.int64)
        for i in range(len(keys)):
            out[i] = d[keys[i]]
        return out

    class Table:
        """Exact cleanup table, grown on demand. G[row, c]: chance of the full set with c coupons left;
        H[row, c]: expected wanted skills."""

        def __init__(self, w, wmask, order, rare, C, pmax, point_bonus):
            self.w = np.array(w, np.float64)
            self.n, self.wmask, self.C, self.pmax, self.pb = len(w), int(wmask), C, pmax, point_bonus
            self.order = np.array(order, np.int64)
            self.rare = np.array(rare, np.int64)
            self.d = Dict.empty(key_type=types.int64, value_type=types.int64)
            self.rows = 0
            self.G = np.zeros((1 << 14, C + 1), np.float32)
            self.H = np.zeros((1 << 14, C + 1), np.float32)

        def ensure(self, keys):
            new = _explore(np.unique(np.asarray(keys, np.int64)), self.d, self.rows, self.pmax, self.w, self.n,
                           self.wmask, self.order, self.rare, self.pb)
            if not len(new):
                return
            need = self.rows + len(new)
            if need > len(self.G):
                cap = max(need, 2 * len(self.G))
                for name in ("G", "H"):
                    a = np.zeros((cap, self.C + 1), np.float32)
                    a[:self.rows] = getattr(self, name)[:self.rows]
                    setattr(self, name, a)
            self.rows = need
            new = new[np.argsort(-(new & ((1 << PBITS) - 1)), kind="stable")]
            _fill(new, self.d, self.G, self.H, self.C, self.w, self.n, self.wmask, self.order, self.rare, self.pb)

        def rows_of(self, keys):
            return _rows(np.asarray(keys, np.int64), self.d)

    CODES = {"at30": 0, "coursier": 1, "once": 2, "hard": 3, "natural": 4, "coursier_v2": 6}

    class Evaluator:
        """Plans for one horse state (Training, boosts, level, learned skills, points, tickets); the cleanup
        table can be shared between evaluators of the same horse, wanted set and point bonus."""

        def __init__(self, horse, M, max_budget=40, tickets=0, start_level=1, learned=(), wanted=None,
                     fodder=None, point_bonus=0.25, points=0, max_level=30, table=None):
            pool = list(horse.weights)
            idx = {s: i for i, s in enumerate(pool)}
            w = [float(horse.weights[s]) for s in pool]
            wanted = set(H.TRAVEL_SET if wanted is None else wanted) & set(pool)
            fod = [s for s in (H.CLASSIC_FODDER if fodder is None else fodder) if s in idx and s not in wanted]
            cyc = H._cycle_skill(fod, horse.weights)
            order = sorted(range(len(pool)), key=lambda i: (w[i], i))
            wmask = sum(1 << idx[s] for s in wanted)
            lmask = sum(1 << idx[s] for s in set(learned) if s in idx)
            self.rare = [i for i in order if wmask >> i & 1]
            self.args = (np.array(w), len(pool), float(horse.W), float(M))
            self.masks = (np.int64(lmask), np.int64(wmask), np.array([idx[s] for s in fod] or [-1], np.int64)[:len(fod)],
                          idx[cyc] if cyc else -1, np.array(order, np.int64), np.array(self.rare, np.int64))
            self.C, self.tickets, self.start_level, self.points = max_budget, tickets, start_level, points
            self.pb, self.max_level, self.n_wanted = point_bonus, max_level, len(wanted)
            self.table = table or Table(w, wmask, order, self.rare, C=max_budget, pmax=points + max_budget,
                                        point_bonus=point_bonus)

        def plan(self, strategy, swap_from=1, spend_cap=0, runs=4000, seed=1):
            """Same output as bdo.horses.simulate_plan: full[B], wanted[B] for B = 0..max_budget (None below
            spend_cap), skills (average skills at 30)."""
            st = CODES[strategy]
            if st == 0:
                spend_cap = 0
            w, n, W, M = self.args
            lmask, wmask, fod, cyc, order, rare = self.masks
            S, base, pts = _many30(runs, seed, w, n, W, M, st, swap_from, spend_cap, self.tickets, self.start_level,
                                   lmask, wmask, fod, cyc, order, rare, self.pb, self.points, self.max_level)
            counts = np.array([bin(int(x)).count("1") for x in S])
            nbud = self.C + 1
            res = {"skills": float(counts.mean()), "wanted_total": self.n_wanted}
            if st == 4:
                hw = np.array([bin(int(x) & int(wmask)).count("1") for x in S])
                res["full"] = [float((hw == self.n_wanted).mean())] * nbud
                res["wanted"] = [float(hw.mean())] * nbud
                return res
            keys = (S << PBITS) | pts
            self.table.ensure(keys)
            rows = self.table.rows_of(keys)
            full, wanted = [], []
            for B in range(nbud):
                if B < spend_cap:
                    full.append(None)
                    wanted.append(None)
                    continue
                j = np.minimum(B - base, self.table.C)
                full.append(float(self.table.G[rows, j].mean()))
                wanted.append(float(self.table.H[rows, j].mean()))
            res["full"], res["wanted"] = full, wanted
            return res


def optimize(horse, M, max_budget=40, strategies=("coursier", "coursier_v2"), runs=(1000, 4000), top=6,
             max_close=25, seed=1, progress=None, start_level=1, **kw):
    """Like bdo.horses.optimize, but tries every plan: at30, and each strategy with every start level (from the
    next level to 29) and every spending cap (1 to max_budget). Stage 2 reruns the top and close plans of each
    budget and goal with fresh horses. Returns {plan: result} for the stage-2 plans."""
    if not available():
        raise H.DataError("the fast engine needs numba (pip install -r requirements-optional.txt)")
    ev = Evaluator(horse, M, max_budget=max_budget, start_level=start_level, **kw)
    plans = [("at30", 1, 0)] + [(st, lv, cap) for st in strategies for lv in range(start_level + 1, 30)
                                for cap in range(1, max_budget + 1)]
    s1 = {}
    for i, p in enumerate(plans):
        s1[p] = ev.plan(*p, runs=runs[0], seed=seed)
        if progress:
            progress("search", i + 1, len(plans))
    keep = {("at30", 1, 0)}
    for B in range(max_budget + 1):
        for goal, margin in (("full", 0.025), ("wanted", 0.08)):
            ok = [p for p in plans if s1[p][goal][B] is not None]
            ranked = sorted(ok, key=lambda p: -s1[p][goal][B])
            keep.update(ranked[:top])
            keep.update([p for p in ranked if s1[p][goal][B] >= s1[ranked[0]][goal][B] - margin][:max_close])
    return {p: ev.plan(*p, runs=runs[1], seed=seed + 1000) for p in sorted(keep)}
