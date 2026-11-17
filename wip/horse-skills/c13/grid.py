import sys, json, itertools; sys.path.insert(0, '/home/claude/bdo-tools')
from multiprocessing import Pool
from bdo import horses as H
SC = {  # report scenarios, least to most favourable
    "F1": ("T8 example (bdolytics icon horse_71)", 16.8, 0, 0),
    "F2": ("Mythical Diné", 21.7, 0, 0),
    "F3": ("Doom (T9)", 21.7, 0, 0),
    "F5": ("Mythical Diné", 21.7, 1, 1),
    "F6": ("Mythical Diné", 100, 0, 0),
}
MAXB = 40
d = H.load_data()
def job(k):
    sc, lv = k
    hn, tb, g, b = SC[sc]
    h = H.get_horse(d, hn); M = h.M(tb, g, b)
    out = {}
    for cap in range(0, MAXB + 1):
        st = "at30" if cap == 0 else "coursier"
        if cap == 0 and lv != 1:
            continue
        r = H.simulate_plan(h, M, st, lv, cap, MAXB, runs=1000, seed=1)
        out[cap] = r["full"]
    return [sc, lv, out]
if __name__ == "__main__":
    keys = list(itertools.product(SC, range(1, 30)))
    with Pool(2) as p:
        res = p.map(job, keys, chunksize=1)
    json.dump(res, open("/home/claude/scratch/c13/grid.json", "w"))
    print("done", len(res))
