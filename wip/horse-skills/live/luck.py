"""How lucky was the live horse? The guide's plan from its level-4 state (reset on a hit, one pass per level, V0
until 15 learned then V2, at most 25 coupons while leveling, tickets on empty level-ups from level 20), simulated;
the user's horse compared with the distribution. Usage: python3 -I luck.py [runs]"""
import random
import sys
sys.path.insert(0, "/home/claude/bdo-tools")
from bdo import horses as H

d = H.load_data(); h = H.get_horse(d, "Mythical Diné"); res = H.skill_resolver(d)
M = h.M(H.training_bonus("Artisan 8"), 0, 0); wt = h.weights; pool = list(wt)
wanted = set(H.TRAVEL_SET) & set(pool); rank = {s: (wt[s], i) for i, s in enumerate(pool)}
fod = [s for s in H.CLASSIC_FODDER if s in wt]; cyc = H._cycle_skill(fod, wt)
L0 = {res(s) for s in ("Saut haut", "Recul rapide", "Hurlement de cheval")}


def run(rng):
    have, pts, spent, t, latched = set(L0), 2, 0, 4, False
    empty = 0                                         # level-ups (first draw) that taught nothing, levels 5..26
    full_at = full_coupons = None
    learned = {}

    def swap(out):
        nonlocal pts, spent
        cands = [s for s in pool if s not in have and s != out]
        if not cands:
            return
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
        pts = 0 if new == tgt else pts + 1

    for lvl in range(4, 30):
        first = True
        while True:
            un = [s for s in pool if s not in have]; su = sum(wt[s] for s in un)
            k = min(M / (su + h.W), 1 / su) if su else 0
            x, got = rng.random(), None
            for s in un:
                x -= k * wt[s]
                if x < 0:
                    got = s
                    break
            if first and not got and lvl + 1 <= 26:
                empty += 1
            first = False
            if got or t == 0 or lvl + 1 < 20:
                break
            t -= 1
        if got:
            have.add(got)
        if lvl + 1 >= 5 and spent < 25 and not wanted <= have:
            if len(have) >= 15:
                latched = True
            for s in (fod if not latched else [cyc]):
                if s in have and spent < 25 and not wanted <= have:
                    swap(s)
        learned[lvl + 1] = len(have)
        if full_at is None and wanted <= have:
            full_at, full_coupons = lvl + 1, spent
    if full_at is None:                               # level-30 cleanup
        while not wanted <= have and spent < 49:
            out = H._rarest_unwanted(have, wanted, rank)
            if out is None:
                break
            swap(out)
        if wanted <= have:
            full_at, full_coupons = 30, spent
    return full_at, full_coupons, empty, learned


N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
rng = random.Random(26)
out = [run(rng) for _ in range(N)]
share = lambda f: 100 * sum(1 for o in out if f(o)) / N
print(f"full set: {share(lambda o: o[0] is not None):.2f}%")
out = [o for o in out if o[0] is not None]; N = len(out)
print(f"level reached with the full set: average {sum(o[0] for o in out) / N:.1f} | by level 25 or earlier: {share(lambda o: o[0] <= 25):.0f}% | 26: {share(lambda o: o[0] == 26):.0f}% | later: {share(lambda o: o[0] > 26):.0f}%")
cs = sorted(o[1] for o in out)
print(f"coupons used for it: average {sum(cs) / N:.1f} | median {cs[N // 2]} | 18 or fewer: {share(lambda o: o[1] <= 18):.0f}% | 13 or fewer: {share(lambda o: o[1] <= 13):.0f}%")
print(f"empty level-ups (first try) from level 5 to 26: average {sum(o[2] for o in out) / N:.1f} | 8 or more: {share(lambda o: o[2] >= 8):.0f}%")
for L, mine in ((10, 8), (14, 10), (18, 13), (20, 14), (24, 18), (26, 20)):
    print(f"learned skills at level {L}: you {mine}, average {sum(o[3][L] for o in out) / N:.1f}, horses with fewer than you {share(lambda o: o[3][L] < mine):.0f}%, as many or more {share(lambda o: o[3][L] >= mine):.0f}%")
print(f"all 20 learnable skills by level 26: {share(lambda o: o[3][26] >= 20):.0f}%")
