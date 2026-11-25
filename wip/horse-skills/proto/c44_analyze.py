"""C44 analysis: for each case and total number of items n (coupons + tickets), the split with the best full-set
chance, the splits within TOL points of it (how flat the optimum is), and what fixed splits lose (all coupons, 1:1,
the best fixed share of tickets per target set). Splits with more than 25 tickets or 40 coupons weren't run.
Usage (repo root): python3 -I wip/horse-skills/proto/c44_analyze.py wip/horse-skills/proto/c44_split_out.txt
"""
import sys
from collections import defaultdict

TOL = 1.0
TOTALS = (5, 10, 15, 20, 25, 30, 35, 40)


def load(path):
    v = {}
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or line.startswith("set\t"):
            continue
        s, h, tr, B, t, full, stuck, used, tu = line.rstrip("\n").split("\t")
        v[(s, h, tr, int(B), int(t))] = (float(full), float(stuck), float(used), float(tu))
    return v


def main(path):
    v = load(path)
    cases = sorted({k[:3] for k in v})
    best = {}
    print(f"# per case: total n -> best tickets t (coupons n - t), full set; t within {TOL} point of the best; "
          "all coupons; 1:1")
    print("set\thorse\ttraining\tn\tbest t\tbest full\tt within tol\tall coupons\t1:1 (t = n // 2)\tstuck best / all coupons")
    for c in cases:
        for n in TOTALS:
            sp = {t: v[c + (n - t, t)] for t in range(0, min(n, 25) + 1) if c + (n - t, t) in v}
            tb = max(sp, key=lambda t: sp[t][0])
            near = [t for t in sp if sp[t][0] >= sp[tb][0] - TOL]
            best[c + (n,)] = (tb, sp)
            print(f"{c[0]}\t{c[1]}\t{c[2]}\t{n}\t{tb}{' (edge)' if tb == max(sp) and tb < n else ''}\t{sp[tb][0]:.1f}\t"
                  f"{min(near)}-{max(near)}\t{sp[0][0]:.1f}\t{sp[n // 2][0]:.1f}\t{sp[tb][1]:.2f} / {sp[0][1]:.2f}")
    print()
    print("# per target set and n: best t (median [range] over the 9 cases); loss vs each case's best (average [max]) of:"
          " all coupons, 1:1, and the best single share f of tickets for that set (t = round(f x n))")
    for s in ("courser", "travel"):
        cs = [c for c in cases if c[0] == s]
        # the best single share f for this set, over every n (minimize the average loss)
        fs = [i / 20 for i in range(0, 13)]
        def loss(f, n, c):
            tb, sp = best[c + (n,)]
            t = min(round(f * n + 1e-9), max(sp))
            return sp[tb][0] - sp[t][0]
        fbest = min(fs, key=lambda f: sum(loss(f, n, c) for n in TOTALS for c in cs))
        print(f"{s}: best single share of tickets f = {fbest:.2f}")
        print("n\tbest t median [range]\tall coupons: avg [max]\t1:1: avg [max]\tf share: avg [max]")
        for n in TOTALS:
            tbs = sorted(best[c + (n,)][0] for c in cs)
            l0 = [loss(0, n, c) for c in cs]
            l1 = [loss(0.5, n, c) for c in cs]
            lf = [loss(fbest, n, c) for c in cs]
            f = lambda xs: f"{sum(xs) / len(xs):.1f} [{max(xs):.1f}]"
            print(f"{n}\t{tbs[len(tbs) // 2]} [{tbs[0]}-{tbs[-1]}]\t{f(l0)}\t{f(l1)}\t{f(lf)}")


if __name__ == "__main__":
    main(sys.argv[1])


def first_k(path):
    """The rule 'the first K items are coupons, the rest tickets (at most 25 tickets: then coupons again)': loss vs
    each case's best split, per set and n, for every K."""
    v = load(path)
    cases = sorted({k[:3] for k in v})
    print()
    print("# rule 'first K coupons, then tickets': loss vs the best split, average [max] over the 9 cases, per n")
    for s in ("courser", "travel"):
        cs = [c for c in cases if c[0] == s]
        print(f"{s}\tK\t" + "\t".join(f"n={n}" for n in TOTALS) + "\tworst")
        for K in range(6, 19):
            row, worst = [], 0
            for n in TOTALS:
                ls = []
                for c in cs:
                    sp = {t: v[c + (n - t, t)][0] for t in range(0, min(n, 25) + 1) if c + (n - t, t) in v}
                    t = min(max(n - K, 0), 25)
                    ls.append(max(sp.values()) - sp[t])
                row.append(f"{sum(ls) / len(ls):.1f} [{max(ls):.1f}]")
                worst = max(worst, max(ls))
            print(f"{s}\t{K}\t" + "\t".join(row) + f"\t{worst:.1f}")


if __name__ == "__main__":
    first_k(sys.argv[1])
