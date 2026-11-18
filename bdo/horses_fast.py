"""Fast engine for horse_skills (optional: needs numba, see requirements-optional.txt).

Same model and plan rules as bdo.horses.simulate_plan, with two differences:
- the leveling is compiled with numba (about 30x faster per core, all cores used);
- the level-30 cleanup is not simulated but computed exactly: for every held-skill set and number of Skill Change
  Points reached, the chance of ending with every wanted skill (and the expected number of wanted skills) with
  c coupons left, under the same cleanup rule (swap the rarest unwanted skill held, desired = rarest missing
  wanted skill). Same averages as simulating it, with much less noise. Plans are evaluated in batches: the batch
  is simulated first, then one sweep over the reachable states, level by level of points, answers all of it.

Random numbers differ from bdo.horses (each simulated horse has its own generator, so results don't depend on the
number of cores): results agree statistically, not number for number.
"""
import numpy as np

try:
    import numba as nb
except ImportError:                                                       # pragma: no cover
    nb = None

from . import horses as H


def available():
    return nb is not None


if nb is not None:
    PBITS = 7                                    # Skill Change Points stored in the low 7 bits of a state key

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
                 rare, pb, points, max_level, switch_at):
        """One horse from start_level to max_level, without the level-30 cleanup.
        st: 0 at30, 1 coursier, 2 once, 3 hard, 4 natural, 6 coursier_v2 (cycles skill 'cyc'), 7 coursier_switch
        (coursier until the horse holds switch_at learned skills, checked once swapping is allowed, then
        coursier_v2 for good).
        Returns (held skills, coupons spent while leveling, Skill Change Points)."""
        a = _mix(np.uint64(seed) * np.uint64(0xD1B54A32D192ED03))
        b = _mix(np.uint64(r) ^ np.uint64(0xA0761D6478BD642F))
        state = np.uint64(a) ^ (np.uint64(b) * np.uint64(0xE7037ED1A0B428DB))
        have = lmask
        spent = 0
        t = tickets
        pts = points
        latched = False
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
            if st == 7 and _pop(have) >= switch_at:
                latched = True
            if st == 1 or (st == 7 and not latched):
                for s in fod:
                    if (have >> s) & 1 and spent < spend_cap:
                        nw, have, state = _swap(s, have, pts, state, w, n, rare, pb)
                        if nw >= 0:
                            spent += 1
                            pts += 1
            elif st == 6 or st == 7:
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
                order, rare, pb, points, max_level, switch_at=0):
        S = np.empty(runs, np.int64)
        base = np.empty(runs, np.int64)
        pts = np.empty(runs, np.int64)
        for r in nb.prange(runs):
            a, b, c = _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask,
                               fod, cyc, order, rare, pb, points, max_level, switch_at)
            S[r] = a
            base[r] = b
            pts[r] = c
        return S, base, pts

    # --- exact level-30 cleanup, swept by Skill Change Points ----------------------------------------------------
    # For an end-of-leveling state (held skills S, points p) and c coupons left, the cleanup rule (swap the rarest
    # unwanted skill held, desired = rarest missing wanted skill) gives exact values: P(missing <= t wanted skills)
    # for t < J (t = 0: the full set), then the expected wanted skills. A coupon always moves p to p + 1, so the
    # states are grouped by points level and computed from the highest level down, two levels in memory at a time.
    # Only points + coupons left <= bound is needed (bound = starting points + largest budget): every value a horse
    # asks for satisfies it, also if the game reset the points (that only lowers them). Values aren't kept between
    # batches: Evaluator.plans simulates a batch of plans first, then one sweep answers all of it.

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
    def _succ(keys, bound, w, n, wmask, order, rare, pb):
        """Successor keys (points p + 1) of the states that can still use a coupon (p < bound)."""
        out = np.empty(len(keys) * n, np.int64)
        m_tot = 0
        nxt = np.empty(n, np.int64)
        prb = np.empty(n, np.float64)
        for k in keys:
            S = k >> PBITS
            p = k & ((1 << PBITS) - 1)
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

    def _levels(start, bound, w, n, wmask, order, rare, pb, chunk=200_000):
        """Sorted keys of every state reachable from the start keys, per points level."""
        start = np.unique(start)
        ps = start & ((1 << PBITS) - 1)
        levels, nxt = {}, np.empty(0, np.int64)
        for p in range(int(ps.min()), bound + 1):
            cur = np.union1d(nxt, start[ps == p])
            levels[p] = cur
            parts = [np.unique(_succ(cur[i:i + chunk], bound, w, n, wmask, order, rare, pb))
                     for i in range(0, len(cur), chunk)]
            nxt = np.unique(np.concatenate(parts)) if parts else np.empty(0, np.int64)
        return levels

    @nb.njit(cache=True, parallel=True)
    def _sweep_level(K, Kn, Vn, V, cmax, J, enc, dec, q, w, n, wmask, order, rare, pb):
        """Values V[row, c, t] of the states K at one points level (c = 0..cmax), from those of the next level
        (keys Kn, values Vn). q: store as 16-bit fixed point (value x enc[t], rounded); read back with dec[t]."""
        nW = _pop(wmask)
        for b in nb.prange((len(K) + 4095) // 4096):
            nxt = np.empty(n, np.int64)
            prb = np.empty(n, np.float64)
            rows2 = np.empty(n, np.int64)
            acc = np.empty(J + 1, np.float64)
            for r in range(b * 4096, min(len(K), (b + 1) * 4096)):
                k = K[r]
                S = k >> PBITS
                p = k & ((1 << PBITS) - 1)
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
    def _accumulate(hkeys, base, plan, cap, idx, K, V, dec, C, acc):
        """Adds each horse's values to acc[plan, budget] for every budget from its plan's cap to C."""
        for i in idx:
            r = np.searchsorted(K, hkeys[i])
            for B in range(max(cap[i], base[i]), C + 1):
                for t in range(acc.shape[2]):
                    acc[plan[i], B, t] += V[r, B - base[i], t] * dec[t]

    def cleanup_values(hkeys, base, plan, cap, nplans, C, bound, J, low_memory, w, n, wmask, order, rare, pb):
        """Sums over the horses of each plan of the exact cleanup values, per budget: acc[plan, B, t] (see above).
        hkeys: end-of-leveling keys (held skills << PBITS | points); base: coupons spent while leveling."""
        nv = J + 1
        if low_memory:
            enc = np.full(nv, 65535.0)
            enc[J] = 65535.0 / max(1, _pop(wmask))
            dec, dt = 1.0 / enc, np.uint16
        else:
            enc = dec = np.ones(nv)
            dt = np.float32
        acc = np.zeros((nplans, C + 1, nv))
        levels = _levels(hkeys, bound, w, n, wmask, order, rare, pb)
        hl = hkeys & ((1 << PBITS) - 1)
        Kn, Vn = np.empty(0, np.int64), np.zeros((0, 1, nv), dt)
        for p in sorted(levels, reverse=True):
            K = levels.pop(p)
            V = np.empty((len(K), bound - p + 1, nv), dt)
            _sweep_level(K, Kn, Vn, V, bound - p, J, enc, dec, low_memory, w, n, wmask, order, rare, pb)
            idx = np.nonzero(hl == p)[0]
            if len(idx):
                _accumulate(hkeys, base, plan, cap, idx, K, V, dec, C, acc)
            Kn, Vn = K, V
        return acc

    @nb.njit(cache=True)
    def _popcounts(S):
        out = np.empty(len(S), np.int64)
        for i in range(len(S)):
            out[i] = _pop(S[i])
        return out

    TAILS = 5                                    # with tails=True: P(missing <= 0..4 wanted skills)
    CODES = {"at30": 0, "coursier": 1, "once": 2, "hard": 3, "natural": 4, "coursier_v2": 6, "coursier_switch": 7}

    class Evaluator:
        """Plans for one horse state (Training, boosts, level, learned skills, points, tickets). plans() simulates a
        batch of plans and computes their level-30 cleanup exactly, in one sweep. low_memory: keep the sweep's values
        as 16-bit numbers (less memory, results within about 0.001 points)."""

        def __init__(self, horse, M, max_budget=40, tickets=0, start_level=1, learned=(), wanted=None,
                     fodder=None, point_bonus=0.25, points=0, max_level=30, low_memory=False):
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
            self.low_memory = low_memory

        def plans(self, plans, runs=4000, seed=1, progress=None, label="plans", tails=False):
            """{plan: result} for plans = [(strategy, swap_from, spend_cap, switch_at)], all simulated with the same
            seed (common random numbers). Same result as bdo.horses.simulate_plan: full[B], wanted[B] for
            B = 0..max_budget (None below spend_cap), skills (average skills at 30); with tails=True also
            tails[B] = [P(missing <= t wanted skills) for t = 0..TAILS - 1] (a bit slower)."""
            w, n, W, M = self.args
            lmask, wmask, fod, cyc, order, rare = self.masks
            C, out, batch = self.C, {}, []
            hk, hb, hp, hc = [], [], [], []
            for i, p in enumerate(plans):
                strategy, swap_from, spend_cap, switch_at = p
                st = CODES[strategy]
                if st == 0:
                    spend_cap = 0
                S, base, pts = _many30(runs, seed, w, n, W, M, st, swap_from, spend_cap, self.tickets,
                                       self.start_level, lmask, wmask, fod, cyc, order, rare, self.pb, self.points,
                                       self.max_level, switch_at)
                res = {"skills": float(_popcounts(S).mean()), "wanted_total": self.n_wanted}
                out[p] = res
                if st == 4:                                              # natural: no cleanup
                    miss = self.n_wanted - _popcounts(S & wmask)
                    res["full"], res["wanted"] = [float((miss == 0).mean())] * (C + 1), [float((self.n_wanted - miss).mean())] * (C + 1)
                    if tails:
                        res["tails"] = [[float((miss <= t).mean()) for t in range(TAILS)]] * (C + 1)
                else:
                    hk.append((S << PBITS) | pts)
                    hb.append(base)
                    hp.append(np.full(runs, len(batch), np.int64))
                    hc.append(np.full(runs, spend_cap, np.int64))
                    batch.append((p, spend_cap))
                if progress:
                    progress(label, i + 1, len(plans))
            if batch:
                J = TAILS if tails else 1
                acc = cleanup_values(np.concatenate(hk), np.concatenate(hb), np.concatenate(hp), np.concatenate(hc),
                                     len(batch), C, self.points + C, J, self.low_memory, w, n, wmask, order, rare,
                                     self.pb)
                for j, (p, cap) in enumerate(batch):
                    out[p]["full"] = [float(acc[j, B, 0] / runs) if B >= cap else None for B in range(C + 1)]
                    out[p]["wanted"] = [float(acc[j, B, J] / runs) if B >= cap else None for B in range(C + 1)]
                    if tails:
                        out[p]["tails"] = [[float(acc[j, B, t] / runs) for t in range(J)] if B >= cap else None
                                           for B in range(C + 1)]
            return out

        def plan(self, strategy, swap_from=1, spend_cap=0, runs=4000, seed=1, switch_at=0):
            """One plan (see plans())."""
            p = (strategy, swap_from, spend_cap, switch_at)
            return self.plans([p], runs, seed)[p]


def optimize(horse, M, max_budget=40, strategies=("coursier", "coursier_v2", "coursier_switch"), runs=(1000, 4000),
             top=6, max_close=25, seed=1, progress=None, start_level=1, **kw):
    """Like bdo.horses.optimize, but tries every plan: at30, and each strategy with every start level (from the
    next level to 29) and every spending cap (1 to max_budget). coursier_switch, which also has a threshold
    (H.SWITCH_TS), first gets the caps of H.PLAN_CAPS only, then every cap between the grid neighbors of its best
    and close plans. Stage 2 reruns the top and close plans of each budget and goal with fresh horses, and the
    general rule's plan for every budget (H.rule_plan), with the chances of missing at most 0..4 wanted skills.
    Returns {plan: result} for the stage-2 plans; plan = (strategy, swap_from, spend_cap, switch_at)."""
    if not available():
        raise H.DataError("the fast engine needs numba (pip install -r requirements-optional.txt)")
    ev = Evaluator(horse, M, max_budget=max_budget, start_level=start_level, **kw)
    levels = range(start_level + 1, 30)
    plans = [("at30", 1, 0, 0)]
    for st in strategies:
        if st == "coursier_switch":
            plans += [(st, lv, cap, T) for lv in levels for cap in H.PLAN_CAPS if cap <= max_budget
                      for T in H.SWITCH_TS]
        else:
            plans += [(st, lv, cap, 0) for lv in levels for cap in range(1, max_budget + 1)]
    s1 = {}

    def run(todo, label):
        s1.update(ev.plans([p for p in todo if p not in s1], runs[0], seed, progress, label))

    def promising():
        keep = {("at30", 1, 0, 0)}
        for B in range(max_budget + 1):
            for goal, margin in (("full", 0.025), ("wanted", 0.08)):
                ok = [p for p in s1 if s1[p][goal][B] is not None]
                ranked = sorted(ok, key=lambda p: -s1[p][goal][B])
                keep.update(ranked[:top])
                keep.update([p for p in ranked if s1[p][goal][B] >= s1[ranked[0]][goal][B] - margin][:max_close])
        return keep

    run(plans, "search")
    near = {(st, lv, c2, T) for st, lv, cap, T in promising() if st == "coursier_switch"
            for c2 in H._neighbors(cap, H.PLAN_CAPS, 1, max_budget)}
    run(sorted(near), "refine")
    final = promising() | {H.rule_plan(B, start_level) for B in range(max_budget + 1)}
    return ev.plans(sorted(final), runs[1], seed + 1000, progress, "recheck", tails=True)
