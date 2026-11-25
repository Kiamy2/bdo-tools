"""C40r follow-up: 'behind 0' vs 'always' at equal tickets used (always interpolated between 0-5 and 10 tickets), by set,
budget and tickets; and vs 'always' with the same tickets available.
Usage (repo root): python3 -I wip/horse-skills/proto/c40r_compare.py wip/horse-skills/proto/c40r_out.txt wip/horse-skills/proto/c40r_dense_out.txt"""
import sys, pandas as pd, numpy as np
d = pd.concat([pd.read_csv(f, sep="\t", comment="#", header=None) for f in sys.argv[1:]])
d.columns = ["set","horse","training","B","tickets","policy","full","gain","used","per","stuck","coupons"]
d = d[d.set != "set"]
for c in ["B","tickets","full","gain","used","per","stuck","coupons"]: d[c] = d[c].astype(float)
key = ["set","horse","training","B"]
rows = []
for k, g in d.groupby(key):
    a = g[g.policy == "always"].set_index("tickets").gain.sort_index()
    xs = np.r_[0, a.index.values]; ys = np.r_[0, a.values]
    sa = g[g.policy == "always"].set_index("tickets").stuck
    base_stuck = g.stuck.max() if False else None
    for _, r in g[g.policy == "behind 0.0"].iterrows():
        interp = np.interp(r.used, xs, ys)
        rows.append(dict(zip(key, k), T=r.tickets, used=r.used, behind=r.gain, always_eq=interp,
                         adv=r.gain - interp, always_full=a[r.tickets], loss=a[r.tickets]-r.gain,
                         st_b=r.stuck, st_a=sa[r.tickets]))
x = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(x.groupby(["set","B","T"]).agg(used=("used","mean"), adv_mean=("adv","mean"), adv_min=("adv","min"), adv_max=("adv","max"),
      loss_mean=("loss","mean"), loss_max=("loss","max"), n_pos=("adv", lambda s: (s>0.3).sum()), n=("adv","size")).round(2))
print(x.groupby(["set","T"]).agg(used=("used","mean"), adv=("adv","mean"), adv_min=("adv","min"), loss=("loss","mean"), loss_max=("loss","max")).round(2))
print()
for (s,B,T), g in x.groupby(["set","B","T"]):
    print(f"{s:8}{B:4.0f}{T:4.0f}  used {g.used.mean():.1f}  behind-vs-always(equal used) {g.adv.mean():+.1f} [{g.adv.min():+.1f}, {g.adv.max():+.1f}]  better>0.3: {(g.adv>0.3).sum()}/9 worse<-0.3: {(g.adv<-0.3).sum()}/9   loss vs always(same available) {g.loss.mean():.1f} [{g.loss.min():.1f},{g.loss.max():.1f}]")
