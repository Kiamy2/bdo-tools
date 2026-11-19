"""Live test (user's Mythical Diné): coupons used and learned skills per level with the guide's plan, from the horse's
current state. Plan: from level 5, V0 until 15 learned skills, then V2, at most 25 coupons while leveling; 4 tickets
from level 20 on; level-30 cleanup (rarest unwanted out, desired = rarest missing wanted) until the full set or 49.
Plain Python, desired skill as in bdo.horses; points_reset per argument.
Usage: python3 -I live_plan.py [runs]
"""
import random
import sys
sys.path.insert(0, "/home/claude/bdo-tools")
from bdo import horses as H

d = H.load_data(); h = H.get_horse(d, "Mythical Diné"); res = H.skill_resolver(d)
M = h.M(H.training_bonus("Artisan 8"), 0, 0); wt = h.weights; pool = list(wt)
wanted = set(H.TRAVEL_SET) & set(pool); rank = {s: (wt[s], i) for i, s in enumerate(pool)}
fod = [s for s in H.CLASSIC_FODDER if s in wt]; cyc = H._cycle_skill(fod, wt)
LEARNED0 = {res(s) for s in ("Saut haut", "Recul rapide", "Hurlement de cheval")}
LEVEL0, POINTS0, TICKETS, BUDGET = 4, 2, 4, 49


def run(rng, reset, start=5, T=15, cap=25, ticket_from=20):
    have, pts, spent, t, latched = set(LEARNED0), POINTS0, 0, TICKETS, False
    counts = {LEVEL0: len(have)}

    def swap(out):
        nonlocal pts, spent
        cands = [s for s in pool if s not in have and s != out]
        if not cands:
            return None
        miss = sorted((s for s in wanted if s in cands), key=lambda s: rank[s])
        tgt = miss[0] if miss else None
        ws = [wt[s] * (1 + 0.25 * pts) if s == tgt else wt[s] for s in cands]
        x, new = rng.random() * sum(ws), cands[-1]
        for s, q in zip(cands, ws):
            x -= q
            if x < 0:
                new = s
                break
        have.discard(out); have.add(new); spent += 1
        pts = 0 if reset and new == tgt else pts + 1
        return new

    for lvl in range(LEVEL0, 30):
        while True:
            un = [s for s in pool if s not in have]; su = sum(wt[s] for s in un)
            k = min(M / (su + h.W), 1 / su) if su else 0
            x, got = rng.random(), None
            for s in un:
                x -= k * wt[s]
                if x < 0:
                    got = s
                    break
            if got or t == 0 or lvl + 1 < ticket_from:
                break
            t -= 1
        if got:
            have.add(got)
        if lvl + 1 >= start and spent < cap:
            if len(have) >= T:
                latched = True
            for s in (fod if not latched else [cyc]):
                if s in have and spent < cap:
                    swap(s)
        counts[lvl + 1] = len(have)
    leveling = spent
    while not wanted <= have and spent < BUDGET:
        out = H._rarest_unwanted(have, wanted, rank)
        if out is None or swap(out) is None:
            break
    return leveling, spent, wanted <= have, counts


N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
for reset in (False, True):
    rng = random.Random(5)
    out = [run(rng, reset) for _ in range(N)]
    tot = sorted(o[1] for o in out)
    pct = lambda f: tot[min(N - 1, int(f * N))]
    print(f"{'reset on a hit' if reset else 'no reset'}: full set {100 * sum(o[2] for o in out) / N:.2f}% | coupons used: "
          f"{sum(o[0] for o in out) / N:.1f} while leveling + {sum(o[1] - o[0] for o in out) / N:.1f} at level 30 = "
          f"{sum(tot) / N:.1f} on average | half the horses within {pct(0.5)}, 90% within {pct(0.9)}, 99% within {pct(0.99)}")
    if not reset:
        avg = {L: sum(o[3][L] for o in out) / N for L in range(LEVEL0, 31)}
        print("level | learned skills (innate not counted) | total in the in-game list (+7 innate)")
        for L in range(LEVEL0, 31):
            print(f"{L} | {avg[L]:.1f} | {avg[L] + 7:.1f}")
