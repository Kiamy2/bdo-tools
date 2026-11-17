import sys, json, itertools; sys.path.insert(0, '/home/claude/bdo-tools')
from multiprocessing import Pool
from bdo import horses as H
HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAIN = {"Pro 10": 16.8, "Art 7": 21.7, "Guru 20": 100}
BOOST = {"none": (0, 0), "both": (1, 1)}
COUP = [10, 15, 20, 25, 30, 40]
RULES = [("at30", 0, 1), ("coursier", 5, 1), ("coursier", 8, 15), ("coursier", 12, 15), ("coursier", 5, 20),
         ("coursier", 8, 20), ("once", 3, 15), ("once", 3, 20), ("once", 5, 20), ("hard", 5, 20)]
d = H.load_data()
def job(k):
    hn, tr, bo, cp = k
    h = H.get_horse(d, hn); M = h.M(TRAIN[tr], *BOOST[bo])
    return [k, [H.simulate(h, M, st, cp, runs=4000, seed=2, reserve=r, swap_from=f)["all_wanted"] for st, r, f in RULES]]
if __name__ == "__main__":
    keys = list(itertools.product(HORSES, TRAIN, BOOST, COUP))
    with Pool(2) as p:
        out = p.map(job, keys, chunksize=2)
    json.dump({"rules": RULES, "rows": out}, open("/home/claude/scratch/confirm_grid.json", "w"))
    print("done", len(out))
