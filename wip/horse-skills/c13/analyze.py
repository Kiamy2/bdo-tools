import sys, json, re, glob; sys.path[:0] = ['/home/claude/bdo-tools', '/home/claude/scratch/c13']
from multiprocessing import Pool
from bdo import horses as H
from grid import SC, MAXB
raw = json.load(open("/home/claude/scratch/c13/grid.json"))
full = {}  # (sc) -> {(lv, cap): list}
for sc, lv, out in raw:
    for cap, f in out.items():
        full.setdefault(sc, {})[(lv, int(cap))] = f
plans = sorted(full["F1"])
# references: best per scenario from step 3 (fresh 4000 runs)
ref = {}
for sc, s in {"F1": "s4", "F2": "s0", "F3": "s3", "F5": "s1", "F6": "s2"}.items():
    f = glob.glob(f"/home/claude/scratch/step3/{s}_*.txt")[0]
    ref[sc] = {int(l.split("\t")[0]): float(l.split("\t")[1].rstrip("%")) / 100 for l in open(f) if re.match(r"^\d+\t", l)}
cands = set()
for B in range(1, MAXB + 1):
    ok = [p for p in plans if p[1] <= B]
    gbest = {sc: max(full[sc][p][B] for p in ok) for sc in SC}
    worst = sorted(ok, key=lambda p: max(gbest[sc] - full[sc][p][B] for sc in SC))
    cands.update(worst[:6])
cands = sorted(cands)
d = H.load_data()
def job(k):
    sc, p = k
    hn, tb, g, b = SC[sc]
    h = H.get_horse(d, hn); M = h.M(tb, g, b)
    st = "at30" if p[1] == 0 else "coursier"
    return [sc, p, H.simulate_plan(h, M, st, p[0], p[1], MAXB, runs=4000, seed=7)["full"]]
if __name__ == "__main__":
    with Pool(2) as pool:
        res = pool.map(job, [(sc, p) for sc in SC for p in cands], chunksize=4)
    fresh = {}
    for sc, p, f in res:
        fresh.setdefault(tuple(p), {})[sc] = f
    out = []
    print(f"{len(cands)} candidate plans rechecked")
    print("coupons | safest plan (fresh runs) | worst loss vs each scenario's best | avg loss | per scenario F1 F2 F3 F5 F6 (loss, points) | near-safest range (worst loss within 1 pt)")
    for B in range(1, MAXB + 1):
        ok = [p for p in fresh if p[1] <= B]
        loss = {p: {sc: 100 * (ref[sc][B] - fresh[p][sc][B]) for sc in SC} for p in ok}
        best = min(ok, key=lambda p: (max(loss[p].values()), sum(loss[p].values())))
        wl = max(loss[best].values())
        near = [p for p in ok if max(loss[p].values()) <= wl + 1]
        lv = sorted({p[0] for p in near}); kp = sorted({B - p[1] for p in near})
        name = "at30" if best[1] == 0 else f"start {best[0]}, keep {B - best[1]}"
        print(f"{B:>3} | {name:<20} | {wl:5.1f} | {sum(loss[best].values())/5:4.1f} | " +
              " ".join(f"{loss[best][sc]:5.1f}" for sc in SC) + f" | start {lv[0]}-{lv[-1]}, keep {kp[0]}-{kp[-1]}")
        out.append([B, best, loss[best]])
    json.dump(out, open("/home/claude/scratch/c13/safest.json", "w"))
