import sys, random; sys.path.insert(0, ".")
import replan2 as R
import table_nb as T
S = R.Setup(R.SETTINGS); s = R.SETTINGS

def play_from(plan, seed, level, have, pts, left):
    """play() from a mid-level state, no re-planning; exact score at 30"""
    rnd = random.Random(seed).random
    w, n, wmask, fod = S.w, S.n, S.wmask, S.fod
    st, sf, cap = plan; used = 0
    def swap(out):
        nonlocal have, left, pts, used
        tr = S.CL.transitions(have, pts, out)
        if not tr: return -1
        x = rnd(); new_set = tr[-1][0]
        for c, pr in tr:
            x -= pr
            if x < 0: new_set = c; break
        have = new_set; left -= 1; pts += 1; used += 1
    for lvl in range(level, 30):
        su = sum(w[i] for i in range(n) if not have >> i & 1); k = min(S.M / (su + S.horse.W), 1 / su) if su else 0
        x = rnd()
        for i in range(n):
            if not have >> i & 1:
                x -= k * w[i]
                if x < 0: have |= 1 << i; break
        reached = lvl + 1
        if reached < sf or used >= cap: continue
        if st == "coursier":
            for q in fod:
                if have >> q & 1 and used < cap: swap(q)
        elif st == "coursier_v2":
            if have >> fod[0] & 1 and used < cap: swap(fod[0])
    return S.score(have, pts, left)

# real mid-level states: play the fixed plan to level 15 / 20 and record the state
def state_at(seed, stop):
    rec = {}
    def grab(level, have, left, pts, sd):
        rec["s"] = (level, have, pts, left); raise StopIteration
    s2 = dict(s); s2["checkpoints"] = [stop]
    try: R.play(S, s2, ("coursier_v2", 13, 9), seed, replan_seed=1, decide_fn=grab)
    except StopIteration: pass
    return rec.get("s")
for stop in (15, 20):
    for seed in (11, 12, 13):
        st = state_at(seed, stop)
        if not st: continue
        level, have, pts, left = st
        ev = T.Evaluator(S.horse, S.M, table=S.table, max_budget=left, learned=S.names(have), points=pts, start_level=level)
        for plan in [("coursier_v2", level + 1, left), ("at30", level + 1, 0), ("coursier_v2", min(29, level + 5), left)]:
            pred = ev.plan(*plan, runs=20000, seed=5)["full"][left]
            N = 4000
            act = sum(play_from(plan, 9_000_000 + j, level, have, pts, left) for j in range(N)) / N
            print(f"level {level}, {left} coupons left, {bin(have).count('1')} skills, plan {plan}: evaluator {pred:.1%} | played {act:.1%}")
