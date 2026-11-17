import sys, time; sys.path.insert(0, '/home/claude/bdo-tools')
from bdo import horses as H
d = H.load_data(); h = H.get_horse(d, "Mythical Diné")
M = h.M(21.7, 0, 0)
coupons = [5, 10, 15, 20, 25, 30, 40]
reserves = list(range(0, 13))
t = time.time()
print("coupons\\reserve\t" + "\t".join(map(str, reserves)))
for c in coupons:
    row = [H.simulate(h, M, "coursier", c, runs=4000, seed=1, reserve=r)["all_wanted"] for r in reserves]
    print(f"{c}\t" + "\t".join(f"{x:.0%}" for x in row), flush=True)
print("at30 ref:", [f"{H.simulate(h, M, 'at30', c, runs=4000, seed=1)['all_wanted']:.0%}" for c in coupons])
print(f"{time.time()-t:.0f}s", file=sys.stderr)
