import sys, json, random; sys.path.insert(0, ".")
import replan2 as R
import table_nb as T
exec(open("midstate_check.py").read().split("# real mid-level states")[0].split("S = R.Setup")[1].join(["S = R.Setup", ""]) if False else "")
S = R.Setup(R.SETTINGS); s = R.SETTINGS
src = open("midstate_check.py").read()
exec(src[src.index("def play_from"):src.index("# real mid-level states")])
recs = []
def recorder_factory(i):
    prev = {"plan": ("coursier_v2", 13, 9), "used_at_adopt": 0}
    def dec(level, have, left, pts, seed):
        chosen, ch = R.decide(S, s, level, have, left, pts, seed)
        st, sf, cap = prev["plan"]
        used = (s["coupons"] - left) - prev["used_at_adopt"]
        cont = (st, max(sf, level + 1), max(cap - used, 0)) if st != "at30" else ("at30", level + 1, 0)
        if cont[0] != "at30" and cont[2] == 0:
            cont = ("at30", level + 1, 0)
        recs.append((level, have, pts, left, chosen, cont))
        prev["plan"] = chosen; prev["used_at_adopt"] = s["coupons"] - left
        return chosen, ch
    return dec
for i in range(60):
    hs = s["seed"] * 1_000_003 + i
    R.play(S, s, ("coursier_v2", 13, 9), hs, replan_seed=s["seed"] % 100000 * 10_000 + i, decide_fn=recorder_factory(i))
diff_ev, diff_pl, n = 0, 0, 0
out = []
for level, have, pts, left, chosen, cont in recs:
    if tuple(chosen) == tuple(cont): continue
    ev = T.Evaluator(S.horse, S.M, table=S.table, max_budget=left, learned=S.names(have), points=pts, start_level=level)
    e1 = ev.plan(*chosen, runs=20000, seed=77)["full"][left]; e0 = ev.plan(*cont, runs=20000, seed=77)["full"][left]
    N = 3000
    p1 = sum(play_from(chosen, 5_000_000 + j, level, have, pts, left) for j in range(N)) / N
    p0 = sum(play_from(cont, 5_000_000 + j, level, have, pts, left) for j in range(N)) / N
    diff_ev += e1 - e0; diff_pl += p1 - p0; n += 1
    out.append((level, left, chosen, cont, e1 - e0, p1 - p0))
print(f"{len(recs)} decisions, {n} where re-planning changed the plan")
print(f"average advantage of the chosen plan over 'continue': evaluator {100*diff_ev/n:+.2f} points, played {100*diff_pl/n:+.2f} points")
for r in out[:15]:
    print(f"  level {r[0]}, {r[1]} left: chose {r[2]} vs continue {r[3]}: evaluator {100*r[4]:+.1f}, played {100*r[5]:+.1f}")
