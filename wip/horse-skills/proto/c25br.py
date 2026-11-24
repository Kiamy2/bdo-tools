"""C25br (2026-11-24): with a Selection Coupon planned, does the best leveling plan differ from the general rule's?
The full rerun of C25b (the cheap check is in c25r.py), on the current engine (points reset, when_stuck = stop) and
target sets.

Cases as c25r.py (no boosts, from level 1). For each case: the C37r plan grid (S1 / S2 / S1-S2 with every start level
2-29, every spending cap 1-24 + 26 / 30 / 35 / 40 up to the largest budget, thresholds 9-17; at30), every plan with
the coupon planned (every Change Coupon aims at the second rarest missing skill, the coupon fills the last one),
1,000 horses; per budget, the 10 best plans, the rule's plan and at30 rechecked with 20,000 fresh horses. Reports the
best rechecked plan, the rule's plan, the rule's loss, and the kind of the best plans (strategy, start level, keep).

Usage (repo root): python3 -I wip/horse-skills/proto/c25br.py > wip/horse-skills/proto/c25br_out.txt
"""
import sys
import time
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

sys.path.insert(0, "wip/horse-skills/proto")
from c25r import CASES, BUDGETS                                          # noqa: E402

RUNS1, RUNS2, SEED = 1000, 20000, 2601
CAPS = list(range(1, 25)) + [26, 30, 35, 40]
TS = list(range(9, 18))
CHUNK = 1500


def grid(bmax):
    caps = [c for c in CAPS if c <= bmax]
    return ([("coursier", s, c, 0) for s in range(2, 30) for c in caps]
            + [("coursier_v2", s, c, 0) for s in range(2, 30) for c in caps]
            + [("coursier_switch", s, c, T) for s in range(2, 30) for c in caps for T in TS] + [("at30", 1, 0, 0)])


def evaluate(ev, plans, runs, seed, **kw):
    out = {}
    for i in range(0, len(plans), CHUNK):
        out.update(ev.plans(plans[i:i + CHUNK], runs, seed, coupon="planned", **kw))
    return out


def main():
    d = H.load_data()
    print(f"# C25br: best plan vs the rule's with a Selection Coupon planned (fast engine, reset, when_stuck stop; "
          f"{RUNS1} horses per plan, the top 10 + rule + at30 rechecked with {RUNS2}; seeds {SEED} / {SEED + 1})")
    print("set\thorse\ttraining\tB\tplans\tbest\trule\trule loss\tat30\tbest plan\t2nd\t3rd")
    for wset, tr, name in CASES:
        t0 = time.time()
        h = H.get_horse(d, name)
        M = h.M(H.training_bonus(tr))
        wanted = H.WANTED_SETS[wset]
        bmax = max(BUDGETS[wset])
        ev = F.Evaluator(h, M, max_budget=bmax, wanted=wanted)
        plans = grid(bmax)
        s1 = evaluate(ev, plans, RUNS1, SEED)
        cand = {("at30", 1, 0, 0)}
        for B in BUDGETS[wset]:
            ok = [p for p in plans if s1[p]["full"][B] is not None]
            cand.update(sorted(ok, key=lambda p: -s1[p]["full"][B])[:10])
            cand.add(H.rule_plan(B, 1, wanted))
        r = evaluate(ev, sorted(cand), RUNS2, SEED + 1)
        for B in BUDGETS[wset]:
            rp = H.rule_plan(B, 1, wanted)
            top = sorted((p for p in r if r[p]["full"][B] is not None), key=lambda p: -r[p]["full"][B])
            b = top[0]
            name3 = [f"{H.plan_name(p, B)} ({100 * r[p]['full'][B]:.1f})" for p in top[:3]]
            print(f"{wset}\t{name}\t{tr}\t{B}\t{len(plans)}\t{100 * r[b]['full'][B]:.1f}\t{100 * r[rp]['full'][B]:.1f}\t"
                  f"{100 * (r[b]['full'][B] - r[rp]['full'][B]):.1f}\t{100 * r[('at30', 1, 0, 0)]['full'][B]:.1f}\t"
                  + "\t".join(name3))
        print(f"# {name} {tr}: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
