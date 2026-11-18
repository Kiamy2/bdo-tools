"""C33 cycle-choice + C35 coursier-variants: which fodder skill to cycle, and V2 + swap-once, vs V2 and plain Coursier.
Every start level 2-29 and spending cap 1-40, 2000 horses each; then for each budget the top 5 of each family are
rerun with 8000 fresh horses. Cleanup: exact table, 'rarest' rule. Output: c33_results.json."""
import sys, os, json, time
sys.path[:0] = ["/home/claude/bdo-tools", os.path.dirname(os.path.abspath(__file__))]
from bdo import horses as H
import table_nb as T
SC = [("F1", "T8 example (bdolytics icon horse_71)", 16.8, 0, 0), ("F2", "Mythical Diné", 21.7, 0, 0),
      ("F3", "Doom (T9)", 21.7, 0, 0), ("F5", "Mythical Diné", 21.7, 1, 1), ("F6", "Mythical Diné", 100, 0, 0)]
FAM = ["coursier", "coursier_v2", "cycle_fc", "cycle_first", "v2_once"]
C = 40
d = H.load_data()
out = {}
tables = {}
for sc, hn, tb, g, b in SC:
    t0 = time.time()
    h = H.get_horse(d, hn)
    if hn not in tables:
        tables.clear()                                  # free the previous horse's table
    ev = T.Evaluator(h, h.M(tb, g, b), table=tables.get(hn), max_budget=C)
    tables[hn] = ev.table
    plans = [("at30", 1, 0)] + [(f, L, cap) for f in FAM for L in range(2, 30) for cap in range(1, C + 1)]
    s1 = {p: ev.plan(*p, runs=1000, seed=1)["full"] for p in plans}
    keep = {("at30", 1, 0)}
    for B in range(1, C + 1):
        for f in FAM:
            ok = [p for p in plans if p[0] == f and s1[p][B] is not None]
            keep.update(sorted(ok, key=lambda p: -s1[p][B])[:5])
    s2 = {p: ev.plan(*p, runs=4000, seed=1001) for p in keep}
    res = {}
    for B in range(1, C + 1):
        row = {}
        for f in ["at30"] + FAM:
            ok = [p for p in s2 if p[0] == f and s2[p]["full"][B] is not None]
            if not ok:
                continue
            best = max(ok, key=lambda p: s2[p]["full"][B])
            row[f] = {"chance": s2[best]["full"][B], "wanted": s2[best]["wanted"][B], "start": best[1],
                      "keep": B - best[2] if f != "at30" else B}
        res[B] = row
    out[sc] = res
    print(f"{sc} done in {time.time() - t0:.0f}s, table {ev.table.rows} entries", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "c33_results.json"), "w"))
