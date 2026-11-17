import sys, json, itertools; sys.path.insert(0, '/home/claude/bdo-tools')
from multiprocessing import Pool
from bdo import horses as H
HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAIN = {"Pro 10": 16.8, "Art 7": 21.7, "Guru 20": 100}
BOOST = {"none": (0, 0), "both": (1, 1)}
COUP = [10, 15, 20, 25, 30]
STRAT = ["coursier", "once"]
FROM = [1, 5, 10, 15, 20, 25, 30]
d = H.load_data()
def job(k):
    hn, tr, bo, cp, st = k
    h = H.get_horse(d, hn); M = h.M(TRAIN[tr], *BOOST[bo])
    return [k, [H.simulate(h, M, st, cp, runs=2000, seed=1, reserve=1, swap_from=f)["all_wanted"] for f in FROM]]
if __name__ == "__main__":
    keys = list(itertools.product(HORSES, TRAIN, BOOST, COUP, STRAT))
    with Pool(2) as p:
        out = p.map(job, keys, chunksize=3)
    json.dump({"from": FROM, "rows": out}, open("/home/claude/scratch/swapfrom_grid.json", "w"))
    print("done", len(out))
