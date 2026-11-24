"""C40r (2026-11-24): when to use Level Down Tickets, with the points reset and stuck horses stopping (when_stuck stop).

Policies (horses_fast.Evaluator ticket options), the same horses for every policy (common random numbers):
  none       no tickets,
  always     on every level-up that teaches nothing (the tool's default),
  from L     the same, from level L on (L = 5, 10, 15, 20, 25),
  behind d   only while the horse has fewer learned skills than the plan's average at that level minus d, the average
             of the same plan without tickets (ref none: d = 0, 0.5, 1, 2) or with tickets always (ref always: d = 0, 1).
Cases: courser set: T8 Types 1, 2, 4; travel set: Mythical Diné, Doom, Arduanatt; x Beginner 1 / Skilled 1 / Artisan 7;
no boosts, from level 1, the general rule's plan; budgets 5 / 10 / 15 (courser), 10 / 20 / 30 (travel); 2 / 5 / 10
tickets. Fast engine (exact cleanup), 20,000 horses.

Usage (repo root): python3 -I wip/horse-skills/proto/c40r.py > wip/horse-skills/proto/c40r_out.txt
"""
import sys
import time
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

RUNS, SEED = 20000, 4001
TRAINING = ("Beginner 1", "Skilled 1", "Artisan 7")
CASES = ([("courser", t, h) for h in ("T8 Type 1", "T8 Type 2", "T8 Type 4") for t in TRAINING]
         + [("travel", t, h) for h in ("Mythical Diné", "Mythical Doom", "Mythical Arduanatt") for t in TRAINING])
BUDGETS = {"courser": (5, 10, 15), "travel": (10, 20, 30)}
TICKETS = (2, 5, 10)
POLICIES = ([("always", {})] + [(f"from {L}", {"ticket_from": L}) for L in (5, 10, 15, 20, 25)]
            + [(f"behind {d}", {"ticket_behind": d}) for d in (0.0, 0.5, 1.0, 2.0)]
            + [(f"behind {d} (ref always)", {"ticket_behind": d, "ticket_ref": "always"}) for d in (0.0, 1.0)])


def main():
    d = H.load_data()
    print(f"# C40r: ticket policies (fast engine, reset, when_stuck stop, {RUNS} horses, seed {SEED}, the rule's plan)")
    print("set\thorse\ttraining\tB\ttickets\tpolicy\tfull set\tgain vs none\ttickets used\tgain per ticket\tstuck\t"
          "coupons used")
    for wset, tr, name in CASES:
        t0 = time.time()
        h = H.get_horse(d, name)
        M = h.M(H.training_bonus(tr))
        wanted = H.WANTED_SETS[wset]
        bmax = max(BUDGETS[wset])
        plans = sorted({H.rule_plan(B, 1, wanted) for B in BUDGETS[wset]})
        none = F.Evaluator(h, M, max_budget=bmax, wanted=wanted).plans(plans, RUNS, SEED, used=True)
        for tk in TICKETS:
            for pname, pol in POLICIES:
                r = F.Evaluator(h, M, max_budget=bmax, wanted=wanted, tickets=tk, **pol).plans(plans, RUNS, SEED,
                                                                                                 used=True)
                for B in BUDGETS[wset]:
                    p = H.rule_plan(B, 1, wanted)
                    x, z = r[p], none[p]
                    g = x["full"][B] - z["full"][B]
                    tu = x["tickets_used"]
                    print(f"{wset}\t{name}\t{tr}\t{B}\t{tk}\t{pname}\t{100 * x['full'][B]:.2f}\t{100 * g:.2f}\t{tu:.2f}\t"
                          f"{100 * g / tu if tu else 0:.2f}\t{100 * x['stuck']:.2f}\t{x['used'][B]:.2f}")
        for B in BUDGETS[wset]:
            p = H.rule_plan(B, 1, wanted)
            print(f"{wset}\t{name}\t{tr}\t{B}\t0\tnone\t{100 * none[p]['full'][B]:.2f}\t0.00\t0.00\t0.00\t"
                  f"{100 * none[p]['stuck']:.2f}\t{none[p]['used'][B]:.2f}")
        print(f"# {name} {tr}: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
