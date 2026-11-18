"""Replays horses from replan.py with a trace (same seeds, so it must reproduce the recorded results)."""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replan as R

def trace_play(S, s, plan, horse_seed, replan_seed=None, decide_fn=None):
    rnd = random.Random(horse_seed).random
    w, n, wmask, order, fod, rare = S.w, S.n, S.wmask, S.order, S.fod, S.rare
    full = (1 << n) - 1
    have, left, pts = 0, s["coupons"], 0
    st, sf, cap = plan
    used = 0
    pb = s["point_bonus"]
    log = []
    nm = lambda i: S.pool[i] + ("*" if wmask >> i & 1 else "")
    def swap(out):
        nonlocal have, left, pts, used
        free = ~have & ~(1 << out) & full
        target = next((i for i in rare if free >> i & 1), -1)
        boost = 1 + pb * pts
        tot = sum(w[i] * boost if i == target else w[i] for i in range(n) if free >> i & 1)
        if tot == 0: return -1
        x = rnd() * tot; new = -1
        for i in range(n):
            if free >> i & 1:
                new = i; x -= w[i] * boost if i == target else w[i]
                if x < 0: break
        have = (have & ~(1 << out)) | (1 << new); left -= 1; pts += 1; used += 1
        return new
    for lvl in range(1, 30):
        su = sum(w[i] for i in range(n) if not have >> i & 1)
        k = min(S.M / (su + S.W), 1 / su) if su else 0
        x, got = rnd(), -1
        for i in range(n):
            if not have >> i & 1:
                x -= k * w[i]
                if x < 0: got = i; break
        if got >= 0: have |= 1 << got
        reached = lvl + 1; ev = [f"L{reached}: " + (nm(got) if got >= 0 else "-")]
        if not (reached < sf or used >= cap):
            def sw(q):
                new = swap(q); ev.append(f"swap {S.pool[q]}->{nm(new)}"); return new
            if st == 1:
                for q in fod:
                    if have >> q & 1 and used < cap: sw(q)
            elif st == 2:
                todo = [i for i in order if have >> i & 1 and not wmask >> i & 1] if reached == sf and sf > 1 else [got]
                for q in todo:
                    if q >= 0 and not wmask >> q & 1 and have >> q & 1 and used < cap: sw(q)
            elif st == 3:
                for q in [i for i in order if have >> i & 1 and not wmask >> i & 1]:
                    slot = q
                    while slot >= 0 and not wmask >> slot & 1 and have >> slot & 1 and used < cap: slot = sw(slot)
        if decide_fn and reached in s["checkpoints"] and left > 0 and have & wmask != wmask:
            p, c = decide_fn(reached, have, left, pts, replan_seed * 100 + reached)
            ev.append(f"[re-plan: {R.NAMES[p[0]]} from {p[1]}, spend<={p[2]}, chance {c:.0%}; {left} coupons left]")
            st, sf, cap = p; used = 0
        log.append("; ".join(ev))
    ev = ["L30 cleanup:"]
    for q in [i for i in order if have >> i & 1 and not wmask >> i & 1]:
        slot = q
        while slot >= 0 and not wmask >> slot & 1 and have & wmask != wmask and left > 0:
            o = slot; slot = swap(slot); ev.append(f"{S.pool[o]}->{nm(slot)}")
        if have & wmask == wmask or left == 0: break
    log.append(" ".join(ev))
    res = {"full": int(have & wmask == wmask), "wanted": bin(have & wmask).count("1"), "skills": bin(have).count("1"), "spent": s["coupons"] - left}
    return res, log

S = R.Setup(R.SETTINGS); s = R.SETTINGS
rows = [json.loads(x) for x in open("results_dine_a7_15.jsonl").read().splitlines()]
head, rows = rows[0], rows[1:]
plan = tuple(head["first_plan"]["plan"])
for i in map(int, sys.argv[1:]):
    hs = s["seed"] * 1_000_003 + i
    dec = lambda lv, hv, lf, pt, sd: R.decide(S, s, lv, hv, lf, pt, sd)
    fx, lf = trace_play(S, s, plan, hs)
    rp, lr = trace_play(S, s, plan, hs, replan_seed=s["seed"] % 100000 * 10_000 + i, decide_fn=dec)
    rec = rows[i]
    ok = all(rec["fixed"][k] == fx[k] and rec["replan"][k] == rp[k] for k in fx)
    print(f"===== horse {i}  (replay matches the recorded result: {ok})   * = travel skill")
    split = next((j for j, (a, b) in enumerate(zip(lf, lr)) if a != b.split("; [re-plan")[0]), None)
    for j, (a, b) in enumerate(zip(lf, lr)):
        mark = "  <-- first difference" if j == split else ""
        if j >= (split or 0) - 2:
            print(f"  fixed : {a}\n  replan: {b}{mark}")
        elif j % 9 == 0:
            print(f"  (both): {a}")
    print(f"  RESULT fixed {fx} | replan {rp}")
