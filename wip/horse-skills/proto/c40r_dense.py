"""C40r follow-up (2026-11-25): the same cases, horses and seed as c40r.py, policy 'always' with 1, 3 and 4 tickets, so
'only while behind' can be compared with 'always' at equal tickets used without interpolating between 2, 5 and 10.
Usage (repo root): python3 -I wip/horse-skills/proto/c40r_dense.py > wip/horse-skills/proto/c40r_dense_out.txt
Comparison: c40r_compare.py (reads c40r_out.txt + c40r_dense_out.txt)."""
import sys; sys.path.insert(0, ".")
sys.argv = sys.argv[:1]
import importlib.util
spec = importlib.util.spec_from_file_location("c40r", "wip/horse-skills/proto/c40r.py"); c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
H, F = c.H, c.F
d = H.load_data()
for wset, tr, name in c.CASES:
    h = H.get_horse(d, name); M = h.M(H.training_bonus(tr)); wanted = H.WANTED_SETS[wset]; bmax = max(c.BUDGETS[wset])
    plans = sorted({H.rule_plan(B, 1, wanted) for B in c.BUDGETS[wset]})
    none = F.Evaluator(h, M, max_budget=bmax, wanted=wanted).plans(plans, c.RUNS, c.SEED, used=True)
    for tk in (1, 3, 4):
        r = F.Evaluator(h, M, max_budget=bmax, wanted=wanted, tickets=tk).plans(plans, c.RUNS, c.SEED, used=True)
        for B in c.BUDGETS[wset]:
            p = H.rule_plan(B, 1, wanted); x, z = r[p], none[p]; g = x["full"][B] - z["full"][B]; tu = x["tickets_used"]
            print(f"{wset}\t{name}\t{tr}\t{B}\t{tk}\talways\t{100*x['full'][B]:.2f}\t{100*g:.2f}\t{tu:.2f}\t{100*g/tu if tu else 0:.2f}\t{100*x['stuck']:.2f}\t{x['used'][B]:.2f}", flush=True)
