import sys, json, itertools; sys.path.insert(0, '/home/claude/bdo-tools')
from multiprocessing import Pool
from bdo import horses as H
HORSES = ["Mythical Diné", "Doom (T9)", "T8 example (bdolytics icon horse_71)"]
TRAIN = {"Pro 10": 16.8, "Art 7": 21.7, "Guru 20": 100}
COUP = [10, 15, 20, 25, 30, 40]
STRAT = ["coursier", "once"]
RES = [3, 5, 8, 12, 16]
FROM = [1, 10, 15, 20, 25]
d = H.load_data()
def job(k):
    hn, tr, cp, st = k
    h = H.get_horse(d, hn); M = h.M(TRAIN[tr], 0, 0)
    return [k, [[H.simulate(h, M, st, cp, runs=1500, seed=1, reserve=r, swap_from=f)["all_wanted"] for f in FROM] for r in RES]]
if __name__ == "__main__":
    keys = list(itertools.product(HORSES, TRAIN, COUP, STRAT))
    with Pool(2) as p:
        out = p.map(job, keys, chunksize=2)
    json.dump({"res": RES, "from": FROM, "rows": out}, open("/home/claude/scratch/combo_grid.json", "w"))
    print("done", len(out))
