import sys, json, random; sys.path.insert(0, ".")
import replan2 as R
import table_nb as T
S = R.Setup(R.SETTINGS); s = dict(R.SETTINGS); s["checkpoints"] = [10]
src = open("midstate_check.py").read()
exec(src[src.index("def play_from"):src.index("# real mid-level states")])
L = open("results2_cp10.jsonl").read().splitlines(); head = json.loads(L[0]); rows = [json.loads(x) for x in L[1:]]
fixed = tuple(head["first_plan"])
targets = [r["horse"] for r in rows if r["replan"]["decisions"] and tuple(r["replan"]["decisions"][0][1:4]) in (("coursier_v2", 14, 10), ("coursier_v2", 12, 9))][:8]
tot_ev, tot_pl = 0, 0
for i in targets:
    hs = s["seed"] * 1_000_003 + i
    st = {}
    def grab(level, have, left, pts, sd):
        st["x"] = (level, have, pts, left); raise StopIteration
    try: R.play(S, s, fixed, hs, replan_seed=1, decide_fn=grab)
    except StopIteration: pass
    level, have, pts, left = st["x"]
    chosen = tuple(rows[i]["replan"]["decisions"][0][1:4])
    ev = T.Evaluator(S.horse, S.M, table=S.table, max_budget=left, learned=S.names(have), points=pts, start_level=level)
    e1 = ev.plan(*chosen, runs=100000, seed=3)["full"][left]; e0 = ev.plan(*fixed, runs=100000, seed=3)["full"][left]
    N = 20000
    p1 = sum(play_from(chosen, 7_000_000 + j, level, have, pts, left) for j in range(N)) / N
    p0 = sum(play_from(fixed, 7_000_000 + j, level, have, pts, left) for j in range(N)) / N
    tot_ev += e1 - e0; tot_pl += p1 - p0
    print(f"horse {i}: chose {chosen} vs fixed {fixed}: evaluator {100*e1:.2f} vs {100*e0:.2f} ({100*(e1-e0):+.2f}) | played {100*p1:.2f} vs {100*p0:.2f} ({100*(p1-p0):+.2f}) | experiment diff {100*(rows[i]['replan']['chance']-rows[i]['fixed']['chance']):+.1f}")
print(f"average advantage: evaluator {100*tot_ev/len(targets):+.2f}, played {100*tot_pl/len(targets):+.2f}")
