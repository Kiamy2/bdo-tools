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

    @nb.njit(cache=True, inline="always")
    def _target(free, rare, keep):
        """Desired skill of a coupon: the rarest missing wanted skill; with keep (a Selection Coupon is kept for the
        end), the second rarest when two or more are missing."""
        first = -1
        for i in rare:
            if (free >> i) & 1:
                if not keep:
                    return i
                if first < 0:
                    first = i
                else:
                    return i
        return first

    @nb.njit(cache=True)
    def _swap(out, have, pts, state, w, n, rare, pb):
        return _swap_k(out, have, pts, state, w, n, rare, pb, False)

    @nb.njit(cache=True)
    def _swap_k(out, have, pts, state, w, n, rare, pb, keep):
        """Coupon: replace skill 'out' by a draw among unlearned skills (not 'out'); desired skill (see _target)
        weight x (1 + pb * points). Returns (new skill or -1, have, state)."""
        free = ~have & ~(np.int64(1) << out)
        target = _target(free, rare, keep)
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
    def _swap_r(out, have, pts, state, w, n, rare, pb, keep):
        """Like _swap_k, with Skill Change Points: back to 0 when the coupon gives the desired skill, else + 1.
        Returns (new skill or -1, have, state, points)."""
        free = ~have & ~(np.int64(1) << out)
        target = _target(free, rare, keep)
        new, have, state = _swap_k(out, have, pts, state, w, n, rare, pb, keep)
        if new < 0:
            return new, have, state, pts
        return new, have, state, (0 if new == target else pts + 1)

    @nb.njit(cache=True)
    def _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod, cyc, order,
                 rare, pb, points, max_level, switch_at, keep):
        """One horse from start_level to max_level, without the level-30 cleanup.
        st: 0 at30, 1 coursier, 2 once, 3 hard, 4 natural, 6 coursier_v2 (cycles skill 'cyc'), 7 coursier_switch
        (coursier until the horse holds switch_at learned skills, checked once swapping is allowed, then
        coursier_v2 for good). keep: coupons keep the rarest missing skill for a Selection Coupon (see _target).
        Skill Change Points: + 1 per coupon, back to 0 when it gives the desired skill.
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
                        nw, have, state, pts = _swap_r(s, have, pts, state, w, n, rare, pb, keep)
                        if nw >= 0:
                            spent += 1
            elif st == 6 or st == 7:
                if cyc >= 0 and (have >> cyc) & 1 and spent < spend_cap:
                    nw, have, state, pts = _swap_r(cyc, have, pts, state, w, n, rare, pb, keep)
                    if nw >= 0:
                        spent += 1
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
                            nw, have, state, pts = _swap_r(s, have, pts, state, w, n, rare, pb, keep)
                            if nw >= 0:
                                spent += 1
                elif got >= 0 and not (wmask >> got) & 1 and (have >> got) & 1 and spent < spend_cap:
                    nw, have, state, pts = _swap_r(got, have, pts, state, w, n, rare, pb, keep)
                    if nw >= 0:
                        spent += 1
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
                        slot, have, state, pts = _swap_r(slot, have, pts, state, w, n, rare, pb, keep)
                        if slot >= 0:
                            spent += 1
        return have, spent, pts

    @nb.njit(cache=True, parallel=True)
    def _many30(runs, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask, fod, cyc,
                order, rare, pb, points, max_level, switch_at=0, keep=False):
        S = np.empty(runs, np.int64)
        base = np.empty(runs, np.int64)
        pts = np.empty(runs, np.int64)
        for r in nb.prange(runs):
            a, b, c = _level30(r, seed, w, n, W, M, st, swap_from, spend_cap, tickets, start_level, lmask, wmask,
                               fod, cyc, order, rare, pb, points, max_level, switch_at, keep)
            S[r] = a
            base[r] = b
            pts[r] = c
        return S, base, pts

    # --- exact level-30 cleanup --------------------------------------------------------------------------------
    # For an end-of-leveling state (held skills S, points p) and c coupons left, the cleanup rule (swap the rarest
    # unwanted skill held, desired = rarest missing wanted skill) gives exact values: P(missing <= t wanted skills)
    # for t < J (t = 0: the full set), then the expected wanted skills. A cleanup coupon never lowers the number g
    # of wanted skills held: it either draws an unwanted skill (same g, points p + 1), another wanted skill (g + 1,
    # p + 1) or the desired one (g + 1, points back to 0). So the states are computed by group g from the highest
    # down, and within a group by points from the highest down.
    # Each state only gets values for c = 0..cmax, cmax = C - (fewest coupons used to reach it, those spent while
    # leveling included): that is all a horse can ask for (found by a search from the end-of-leveling states).
    # Values aren't kept between batches: Evaluator.plans simulates a batch of plans first, then one sweep answers
    # all of it.

    PMASK = (1 << PBITS) - 1

    @nb.njit(cache=True)
    def _slot(S, wmask, order):
        for i in order:
            if (S >> i) & 1 and not (wmask >> i) & 1:
                return i
        return -1

    @nb.njit(cache=True)
    def _trans(S, p, out, w, n, rare, pb, nxt, prb):
        return _trans_k(S, p, out, w, n, rare, pb, nxt, prb, False)

    @nb.njit(cache=True)
    def _trans_k(S, p, out, w, n, rare, pb, nxt, prb, keep):
        """Next held-skill sets and their chances for one coupon swapping 'out' (desired skill: see _target)."""
        full = (np.int64(1) << n) - 1
        free = ~S & ~(np.int64(1) << out) & full
        target = _target(free, rare, keep)
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
    def _trans_r(k, out, w, n, rare, pb, nxt, prb, keep):
        """Like _trans_k for the state key k, with the next state keys: points back to 0 if the coupon gives the
        desired skill, else + 1."""
        S = k >> PBITS
        p = k & PMASK
        full = (np.int64(1) << n) - 1
        target = _target(~S & ~(np.int64(1) << out) & full, rare, keep)
        m = _trans_k(S, p, out, w, n, rare, pb, nxt, prb, keep)
        for i in range(m):
            new = nxt[i] & ~S
            nxt[i] = (nxt[i] << PBITS) | (0 if target >= 0 and new == (np.int64(1) << target) else p + 1)
        return m

    @nb.njit(cache=True)
    def _moves(k, wmask, nW, sel, order):
        """Skill a cleanup coupon swaps out in state k, or -1 when the cleanup is over (sel = 1: a Selection Coupon
        is kept for the end, so the cleanup stops at one missing skill and keeps the rarest for it)."""
        S = k >> PBITS
        if nW - _pop(S & wmask) <= sel:
            return -1
        return _slot(S, wmask, order)

    @nb.njit(cache=True, parallel=True)
    def _succ(keys, w, n, wmask, order, rare, pb, sel):
        """Successor keys of the given states (one cleanup coupon), -1 where there are fewer than n."""
        nW = _pop(wmask)
        out = np.full(len(keys) * n, -1, np.int64)
        for j in nb.prange(len(keys)):
            nxt = np.empty(n, np.int64)
            prb = np.empty(n, np.float64)
            o = _moves(keys[j], wmask, nW, sel, order)
            if o >= 0:
                m = _trans_r(keys[j], o, w, n, rare, pb, nxt, prb, sel > 0)
                out[j * n:j * n + m] = nxt[:m]
        return out

    def _reach(hkeys, base, C, w, n, wmask, order, rare, pb, sel=0, chunk=500_000):
        """Sorted keys of every state the cleanup can reach from the end-of-leveling states hkeys (base: coupons
        spent while leveling), and cmax (see above)."""
        o = np.lexsort((base, hkeys))
        hk, hb = hkeys[o], base[o]
        first = np.ones(len(hk), bool)
        first[1:] = hk[1:] != hk[:-1]
        hk, hb = hk[first], hb[first]                       # each key with its fewest coupons spent
        seen, keys, cmax = np.empty(0, np.int64), [], []
        nxt = np.empty(0, np.int64)
        for u in range(int(hb.min()), C + 1):
            cur = np.setdiff1d(np.union1d(nxt, hk[hb == u]), seen, assume_unique=True)
            keys.append(cur)
            cmax.append(np.full(len(cur), C - u, np.int16))
            seen = np.union1d(seen, cur)
            if u == C:
                break
            parts = [np.unique(_succ(cur[i:i + chunk], w, n, wmask, order, rare, pb, sel))
                     for i in range(0, len(cur), chunk)]
            nxt = np.unique(np.concatenate(parts)) if parts else np.empty(0, np.int64)
            nxt = nxt[nxt >= 0]
        keys, cmax = np.concatenate(keys), np.concatenate(cmax)
        o = np.argsort(keys)
        return keys[o], cmax[o]

    @nb.njit(cache=True, parallel=True)
    def _sweep(K, cm, off, V, KA, offA, VA, KB, offB, VB, KZ, offZ, VZ, J, enc, dec, q, w, n, wmask, order, rare,
               pb, sel):
        """Values V[off[r] + c, t] (c = 0..cm[r]) of the states K of one block (wanted skills g, points p), from
        those of the blocks (g, p + 1) (A), (g + 1, p + 1) (B) and (g + 1, 0) (Z): see cleanup_values.
        q: store as 16-bit fixed point (value x enc[t], rounded); read back with dec[t]. With len(enc) = J + 2, the
        last value is the expected number of cleanup coupons used."""
        nW = _pop(wmask)
        nv = len(enc)
        for b in nb.prange((len(K) + 1023) // 1024):
            nxt = np.empty(n, np.int64)
            prb = np.empty(n, np.float64)
            rows = np.empty(n, np.int64)
            blk = np.empty(n, np.int64)
            acc = np.empty(nv, np.float64)
            for r in range(b * 1024, min(len(K), (b + 1) * 1024)):
                k = K[r]
                hw = _pop((k >> PBITS) & wmask)
                miss = nW - hw
                m = 0
                if cm[r] > 0:
                    o = _moves(k, wmask, nW, sel, order)
                    if o >= 0:
                        m = _trans_r(k, o, w, n, rare, pb, nxt, prb, sel > 0)
                for i in range(m):
                    if _pop((nxt[i] >> PBITS) & wmask) == hw:
                        blk[i] = 0
                        rows[i] = offA[np.searchsorted(KA, nxt[i])]
                    elif nxt[i] & PMASK:
                        blk[i] = 1
                        rows[i] = offB[np.searchsorted(KB, nxt[i])]
                    else:
                        blk[i] = 2
                        rows[i] = offZ[np.searchsorted(KZ, nxt[i])]
                for c in range(cm[r] + 1):
                    if c == 0 or m == 0:
                        for t in range(J):
                            acc[t] = 1.0 if miss <= t else 0.0
                        acc[J] = hw
                        if nv > J + 1:
                            acc[J + 1] = 0.0
                    else:
                        for t in range(nv):
                            acc[t] = 0.0
                        for i in range(m):
                            x = rows[i] + c - 1
                            for t in range(nv):
                                if blk[i] == 0:
                                    v = VA[x, t]
                                elif blk[i] == 1:
                                    v = VB[x, t]
                                else:
                                    v = VZ[x, t]
                                acc[t] += prb[i] * (v * dec[t])
                    if nv > J + 1 and c > 0 and m > 0:
                        acc[J + 1] += 1.0
                    for t in range(nv):
                        x = acc[t] * enc[t]
                        if q:
                            x = np.floor(x + 0.5)
                        V[off[r] + c, t] = x

    @nb.njit(cache=True)
    def _accumulate(hkeys, base, plan, cap, idx, K, off, V, dec, C, acc):
        """Adds each horse's values to acc[plan, budget] for every budget from its plan's cap to C."""
        for i in idx:
            r = off[np.searchsorted(K, hkeys[i])]
            for B in range(max(cap[i], base[i]), C + 1):
                for t in range(acc.shape[2]):
                    acc[plan[i], B, t] += V[r + B - base[i], t] * dec[t]

    def cleanup_values(hkeys, base, plan, cap, nplans, C, J, low_memory, w, n, wmask, order, rare, pb, sel=0,
                       stats=None, used=False):
        """Sums over the horses of each plan of the exact cleanup values, per budget: acc[plan, B, t] (see above).
        used: one more value, acc[..., J + 1]: the expected number of Change Coupons the cleanup uses.
        hkeys: end-of-leveling keys (held skills << PBITS | points); base: coupons spent while leveling.
        The states are split in blocks (wanted skills g, points p); block (g, p) needs (g, p + 1), (g + 1, p + 1)
        and (g + 1, 0), so a block of group g + 1 is dropped as soon as group g no longer needs it.
        stats: a dict, filled with the number of states and the most values held at once."""
        if int((hkeys & PMASK).max()) + C > PMASK:
            raise ValueError(f"Skill Change Points above {PMASK}")
        nv = J + 1 + bool(used)
        if low_memory:
            enc = np.full(nv, 65535.0)
            enc[J] = 65535.0 / max(1, _pop(wmask))
            if used:
                enc[J + 1] = 65535.0 / max(1, C)
            dec, dt = 1.0 / enc, np.uint16
        else:
            enc = dec = np.ones(nv)
            dt = np.float32
        acc = np.zeros((nplans, C + 1, nv))
        keys, cmax = _reach(hkeys, base, C, w, n, wmask, order, rare, pb, sel)
        g_all = _popcounts((keys >> PBITS) & wmask)
        hg = _popcounts((hkeys >> PBITS) & wmask)
        hpts = hkeys & PMASK
        groups = {}                                  # g -> {p: (keys, cmax)}, values computed later
        for g in np.unique(g_all):
            s = g_all == g
            K, cm = keys[s], cmax[s]
            ps = K & PMASK
            groups[int(g)] = {int(p): (K[ps == p], cm[ps == p]) for p in np.unique(ps)}
        del keys, cmax, g_all
        empty = (np.empty(0, np.int64), np.zeros(1, np.int64), np.zeros((1, nv), dt))
        done = {}                                    # (g, p) -> (keys, offsets, values)
        held = peak = n_states = 0
        for g in sorted(groups, reverse=True):
            levels = groups.pop(g)
            for p in sorted(levels, reverse=True):
                K, cm = levels.pop(p)
                n_states += len(K)
                off = np.zeros(len(K), np.int64)
                off[1:] = np.cumsum(cm[:-1].astype(np.int64) + 1)
                V = np.empty((int(off[-1]) + int(cm[-1]) + 1, nv), dt)
                held += len(V)
                peak = max(peak, held)
                A, B, Z = (done.get(x, empty) for x in ((g, p + 1), (g + 1, p + 1), (g + 1, 0)))
                _sweep(K, cm, off, V, *A, *B, *Z, J, enc, dec, low_memory, w, n, wmask, order, rare, pb, sel)
                idx = np.nonzero((hg == g) & (hpts == p))[0]
                if len(idx):
                    _accumulate(hkeys, base, plan, cap, idx, K, off, V, dec, C, acc)
                done[(g, p)] = (K, off, V)
                if (g + 1, p + 1) in done:                        # only block (g, p) needed it
                    held -= len(done.pop((g + 1, p + 1))[2])
                del K, cm, off, V, A, B, Z
            for x in [x for x in done if x[0] == g + 1]:          # the rest of group g + 1
                held -= len(done.pop(x)[2])
        if stats is not None:
            stats.update(states=n_states, peak_values=peak * nv)
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

        def plans(self, plans, runs=4000, seed=1, progress=None, label="plans", tails=False, coupon=None,
                  used=False, at_most=False, stuck=False):
            """{plan: result} for plans = [(strategy, swap_from, spend_cap, switch_at)], all simulated with the same
            seed (common random numbers). Same result as bdo.horses.simulate_plan: full[B], wanted[B] for
            B = 0..max_budget (None below spend_cap), skills (average skills at 30); with tails=True also
            tails[B] = [P(missing <= t wanted skills) for t = 0..TAILS - 1] (a bit slower).
            coupon: a Mount Skill Selection Coupon used at the very end (on the last missing skill; the horse needs
            an unwanted skill to change, i.e. at least as many learned skills as wanted ones). 'planned': every
            Change Coupon (leveling and level 30) keeps the rarest missing skill for it (desired skill = the second
            rarest missing); 'fallback': only the level-30 cleanup does (decided at 30); None: no Selection Coupon.
            The 'natural' strategy uses no coupon of any kind.
            used=True: also used[B] = the expected number of Change Coupons used with B coupons available (while
            leveling, then at level 30; the cleanup stops once it's done or can't go on).
            at_most=True: also at_most[B] for every B = 0..max_budget, below spend_cap too: the chance of the full
            set with at most B coupons in total when the plan is followed as planned (its leveling as for its own
            budget, then the cleanup until the full set). It's full[B] from spend_cap on; below, only the horses
            whose leveling spent at most B coupons can count.
            Every result also has stuck: the share of horses reaching max_level with fewer learned skills than
            wanted ones (no Change Coupon can then complete the set: a coupon never changes the skill count).
            stuck=True with used=True: also used_ok[B], the expected coupons used by the horses that aren't stuck."""
            w, n, W, M = self.args
            lmask, wmask, fod, cyc, order, rare = self.masks
            C, out, batch, nW = self.C, {}, [], self.n_wanted
            sel = coupon is not None
            hk, hb, hp, hc = [], [], [], []
            for i, p in enumerate(plans):
                strategy, swap_from, spend_cap, switch_at = p
                st = CODES[strategy]
                if st == 0:
                    spend_cap = 0
                S, base, pts = _many30(runs, seed, w, n, W, M, st, swap_from, spend_cap, self.tickets,
                                       self.start_level, lmask, wmask, fod, cyc, order, rare, self.pb, self.points,
                                       self.max_level, switch_at, coupon == "planned")
                res = {"skills": float(_popcounts(S).mean()), "wanted_total": nW,
                       "stuck": float((_popcounts(S) < nW).mean())}
                out[p] = res
                if st == 4:                                              # natural: no cleanup, no coupon
                    miss = nW - _popcounts(S & wmask)
                    res["full"], res["wanted"] = [float((miss == 0).mean())] * (C + 1), [float((nW - miss).mean())] * (C + 1)
                    if tails:
                        res["tails"] = [[float((miss <= t).mean()) for t in range(TAILS)]] * (C + 1)
                    if used:
                        res["used"] = [0.0] * (C + 1)
                        if stuck:
                            res["used_ok"] = [0.0] * (C + 1)
                    if at_most:
                        res["at_most"] = list(res["full"])
                else:
                    hk.append((S << PBITS) | pts)
                    hb.append(base)
                    hp.append(np.full(runs, len(batch), np.int64))
                    hc.append(np.full(runs, 0 if at_most else spend_cap, np.int64))   # cleanup values from this budget
                    batch.append((p, spend_cap))
                if progress:
                    progress(label, i + 1, len(plans))
            if not batch:
                return out
            hk, hb, hp, hc = map(np.concatenate, (hk, hb, hp, hc))
            nb_ = len(batch)
            T = TAILS if tails else 1
            ok = _popcounts(hk >> PBITS) >= nW                             # not stuck (a spare skill)
            n_ok = np.bincount(hp[ok], minlength=nb_)
            ok_sum = np.bincount(hp[ok], weights=hb[ok], minlength=nb_)      # their coupons spent while leveling
            split = stuck and used
            if not sel and not split:
                acc = cleanup_values(hk, hb, hp, hc, nb_, C, T, self.low_memory, w, n, wmask, order,
                                     rare, self.pb, used=used)
                use = lambda j, B: acc[j, B, T + 1]
                full = lambda j, B: acc[j, B, 0]
                wanted = lambda j, B: acc[j, B, T]
                tail = lambda j, B, t: acc[j, B, t]
            elif not sel:
                # the same values, the horses that aren't stuck in plan j, the stuck ones in j + nb_
                acc = cleanup_values(hk, hb, np.where(ok, hp, hp + nb_), hc, 2 * nb_, C, T, self.low_memory, w, n,
                                     wmask, order, rare, self.pb, used=used)
                use = lambda j, B: acc[j, B, T + 1] + acc[j + nb_, B, T + 1]
                use_ok = lambda j, B: acc[j, B, T + 1]
                full = lambda j, B: acc[j, B, 0] + acc[j + nb_, B, 0]
                wanted = lambda j, B: acc[j, B, T] + acc[j + nb_, B, T]
                tail = lambda j, B, t: acc[j, B, t] + acc[j + nb_, B, t]
            else:
                # horses with a spare skill (j) use the coupon on the last missing skill: their result is the cleanup's
                # (which stops at one missing skill) shifted by one; the others (j + nb_) can't use it
                spare = _popcounts(hk >> PBITS) >= nW
                J = T + 1
                acc = cleanup_values(hk, hb, np.where(spare, hp, hp + nb_), hc, 2 * nb_, C, J,
                                     self.low_memory, w, n, wmask, order, rare, self.pb, 1, used=used)
                use = lambda j, B: acc[j, B, J + 1] + acc[j + nb_, B, J + 1]
                use_ok = lambda j, B: acc[j, B, J + 1]
                n_sp = np.bincount(hp[spare], minlength=nb_)
                full = lambda j, B: acc[j, B, 1] + acc[j + nb_, B, 0]
                wanted = lambda j, B: acc[j, B, J] + n_sp[j] - acc[j, B, 0] + acc[j + nb_, B, J]
                tail = lambda j, B, t: acc[j, B, t + 1] + acc[j + nb_, B, t]
            bsum = np.bincount(hp, weights=hb, minlength=nb_)               # coupons spent while leveling
            for j, (p, cap) in enumerate(batch):
                if used:
                    out[p]["used"] = [float((bsum[j] + use(j, B)) / runs) if B >= cap else None for B in range(C + 1)]
                if split:
                    out[p]["used_ok"] = [float((ok_sum[j] + use_ok(j, B)) / n_ok[j]) if B >= cap and n_ok[j] else None
                                         for B in range(C + 1)]
                out[p]["full"] = [float(full(j, B) / runs) if B >= cap else None for B in range(C + 1)]
                if at_most:                          # below cap, the sums only hold horses that spent <= B leveling
                    out[p]["at_most"] = [float(full(j, B) / runs) for B in range(C + 1)]
                out[p]["wanted"] = [float(wanted(j, B) / runs) if B >= cap else None for B in range(C + 1)]
                if tails:
                    out[p]["tails"] = [[float(tail(j, B, t) / runs) for t in range(T)] if B >= cap else None
                                       for B in range(C + 1)]
            return out

        def learned_by_level(self, plan, runs=4000, seed=1, coupon=None):
            """Average learned skills (innate ones not counted) when reaching each level from start_level to
            max_level, for one plan: {level: average}. Same horses as plans() with the same seed."""
            w, n, W, M = self.args
            lmask, wmask, fod, cyc, order, rare = self.masks
            strategy, swap_from, spend_cap, switch_at = plan
            st = CODES[strategy]
            out = {}
            for L in range(self.start_level, self.max_level + 1):
                S, _, _ = _many30(runs, seed, w, n, W, M, st, swap_from, 0 if st == 0 else spend_cap, self.tickets,
                                  self.start_level, lmask, wmask, fod, cyc, order, rare, self.pb, self.points, L,
                                  switch_at, coupon == "planned")
                out[L] = float(_popcounts(S).mean())
            return out

        def plan(self, strategy, swap_from=1, spend_cap=0, runs=4000, seed=1, switch_at=0, coupon=None):
            """One plan (see plans())."""
            p = (strategy, swap_from, spend_cap, switch_at)
            return self.plans([p], runs, seed, coupon=coupon)[p]


def search_grid(start_level=1, max_cap=40, strategies=("coursier", "coursier_v2", "coursier_switch")):
    """The plans optimize() tries first: at30, and each strategy with every start level (from the next level to 29)
    and every spending cap 1..max_cap (coursier_switch: the caps of H.PLAN_CAPS, every threshold of H.SWITCH_TS)."""
    levels = range(start_level + 1, 30)
    plans = [("at30", 1, 0, 0)]
    for st in strategies:
        if st == "coursier_switch":
            plans += [(st, lv, cap, T) for lv in levels for cap in H.PLAN_CAPS if cap <= max_cap
                      for T in H.SWITCH_TS]
        else:
            plans += [(st, lv, cap, 0) for lv in levels for cap in range(1, max_cap + 1)]
    return plans


def optimize(horse, M, max_budget=40, strategies=("coursier", "coursier_v2", "coursier_switch"), runs=(1000, 4000),
             top=6, max_close=25, seed=1, progress=None, start_level=1, coupon=None, stage1=None, **kw):
    """Like bdo.horses.optimize, but tries every plan: at30, and each strategy with every start level (from the
    next level to 29) and every spending cap (1 to max_budget). coursier_switch, which also has a threshold
    (H.SWITCH_TS), first gets the caps of H.PLAN_CAPS only, then every cap between the grid neighbors of its best
    and close plans. Stage 2 reruns the top and close plans of each budget and goal with fresh horses, and the
    general rule's plan for every budget (H.rule_plan), with the chances of missing at most 0..4 wanted skills
    and the expected coupons used. stage1: a dict to fill with the stage-1 results of every plan tried (then with the
    expected coupons used and the stuck share too, for frontier_plans()).
    coupon: see Evaluator.plans (the search then aims at the full set with the Selection Coupon).
    Returns {plan: result} for the stage-2 plans; plan = (strategy, swap_from, spend_cap, switch_at)."""
    if not available():
        raise H.DataError("the fast engine needs numba (pip install -r requirements-optional.txt)")
    ev = Evaluator(horse, M, max_budget=max_budget, start_level=start_level, **kw)
    plans = search_grid(start_level, max_budget, strategies)
    s1 = {}

    def run(todo, label):
        s1.update(ev.plans([p for p in todo if p not in s1], runs[0], seed, progress, label, coupon=coupon,
                           used=stage1 is not None))

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
    if stage1 is not None:
        stage1.update(s1)
    final = promising() | {H.rule_plan(B, start_level, kw.get("wanted")) for B in range(max_budget + 1)}
    return ev.plans(sorted(final), runs[1], seed + 1000, progress, "recheck", tails=True, coupon=coupon, used=True)
