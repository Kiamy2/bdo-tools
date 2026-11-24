"""C25r (2026-11-24): the Mount Skill Selection Coupon with the points reset, on the current target sets.

For each case (horse x Training, no boosts, from level 1) and budget B: the general rule's plan for B (H.rule_plan) with
  none      no Selection Coupon,
  fallback  the plan as without it, the coupon used at the very end if the horse has an unwanted skill to change
            (from level 30 on, Change Coupons aim at the second rarest missing skill),
  planned   sure to use it: every Change Coupon, while leveling and at level 30, aims at the second rarest missing
            skill; the coupon fills the last one.
Worth = the extra Change Coupons the no-coupon rule plan needs to match the full-set chance (rule plan for B + x,
interpolated between whole coupons). Compared with the price: 12.4 Change Coupons (single prices: 3,100 / 250 Pearls),
13.6 at the 11-for-2,500 bundle (prices checked in game 2026-11-24).
Then the cheap C25b check: the tool's search with the coupon planned (horses_fast.optimize(coupon="planned")), the tied
plans and the rule's plan rechecked on fresh horses: how far the rule's plan is from the best found.
Engine: the tool's fast engine (exact cleanup, points reset, when_stuck = stop), 20,000 horses.

Usage (repo root): python3 -I wip/horse-skills/proto/c25r.py > wip/horse-skills/proto/c25r_out.txt
"""
import sys
import time
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

RUNS, SEED = 20000, 2501
TRAINING = ("Beginner 1", "Skilled 1", "Artisan 7", "Guru 20")
CASES = ([("courser", t, h) for h in ("T8 Type 1", "T8 Type 2", "T8 Type 4", "T8 Type 5") for t in TRAINING]
         + [("travel", t, h) for h in ("Mythical Diné", "Mythical Doom", "Mythical Arduanatt") for t in TRAINING])
BUDGETS = {"courser": (2, 5, 10, 15), "travel": (10, 15, 20, 25, 30)}
EXTRA = 30                      # no-coupon budgets checked beyond B for the worth


def worth(none_by_budget, B, target):
    """Extra coupons x (interpolated) so that the no-coupon rule plan for B + x reaches `target`; None if not reached."""
    prev = none_by_budget[B]
    if prev >= target:
        return 0.0
    for x in range(1, EXTRA + 1):
        cur = none_by_budget.get(B + x)
        if cur is None:
            return None
        if cur >= target:
            return x - 1 + (target - prev) / (cur - prev) if cur > prev else float(x)
        prev = cur
    return None


def main():
    d = H.load_data()
    print("# C25r: Selection Coupon worth with the rule's plan (fast engine, reset, when_stuck stop, "
          f"{RUNS} horses, seed {SEED})")
    print("set\thorse\ttraining\tB\tnone\tfallback\tplanned\tworth fallback\tworth planned\tno spare skill\t"
          "C25b: best planned\trule planned\trule loss\tbest plan (planned)")
    for wset, tr, name in CASES:
        t0 = time.time()
        h = H.get_horse(d, name)
        M = h.M(H.training_bonus(tr))
        wanted = H.WANTED_SETS[wset]
        bmax = max(BUDGETS[wset])
        ev = F.Evaluator(h, M, max_budget=bmax + EXTRA, wanted=wanted)
        rules = {B: H.rule_plan(B, 1, wanted) for B in range(1, bmax + EXTRA + 1)}
        plans = sorted(set(rules.values()))
        r0 = ev.plans(plans, RUNS, SEED)
        none = {B: r0[rules[B]]["full"][B] for B in rules}
        rf = ev.plans(sorted({rules[B] for B in BUDGETS[wset]}), RUNS, SEED, coupon="fallback", stuck=True)
        rp = ev.plans(sorted({rules[B] for B in BUDGETS[wset]}), RUNS, SEED, coupon="planned", stuck=True)
        # C25b: the tool's search with the coupon planned
        res = F.optimize(h, M, bmax, seed=SEED + 7, coupon="planned", wanted=wanted)
        cand = {rules[B] for B in BUDGETS[wset]}
        for B in BUDGETS[wset]:
            cand.update(H.tied_plans(res, B, "full", 0.01)[:12])
        ev2 = F.Evaluator(h, M, max_budget=bmax, wanted=wanted)
        r3 = ev2.plans(sorted(cand), RUNS, SEED + 2000, coupon="planned", tails=True, used=True)
        for B in BUDGETS[wset]:
            p = rules[B]
            fb, pl = rf[p]["full"][B], rp[p]["full"][B]
            wf, wp = worth(none, B, fb), worth(none, B, pl)
            best = max((q for q in r3 if r3[q]["full"][B] is not None), key=lambda q: r3[q]["full"][B])
            fmt = lambda x: f"{x:.1f}" if x is not None else f">{EXTRA}"
            print(f"{wset}\t{name}\t{tr}\t{B}\t{100 * none[B]:.1f}\t{100 * fb:.1f}\t{100 * pl:.1f}\t{fmt(wf)}\t"
                  f"{fmt(wp)}\t{100 * rp[p]['stuck']:.1f}\t{100 * r3[best]['full'][B]:.1f}\t{100 * r3[p]['full'][B]:.1f}\t"
                  f"{100 * (r3[best]['full'][B] - r3[p]['full'][B]):.1f}\t{H.plan_name(best, B)}")
        print(f"# {name} {tr}: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
