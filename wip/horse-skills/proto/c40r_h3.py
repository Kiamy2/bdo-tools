"""C40r H3 (2026-11-24): one more Level Down Ticket or one more Change Coupon (both 250 Pearls)?

For each case and budget B (as c40r.py) and T tickets (0, 2, 5): the rule's plan for B with T tickets (base), then
  +coupon         the rule's plan for B + 1, T tickets,
  +ticket always  the rule's plan for B, T + 1 tickets, used on every level-up that teaches nothing,
  +ticket behind  the rule's plan for B, T + 1 tickets, only while behind the plan's average without tickets (d = 0),
                  against a base with T tickets under the same policy.
Reports the gain in full-set chance and the drop in stuck share for each. Same horses throughout (20,000).

Usage (repo root): python3 -I wip/horse-skills/proto/c40r_h3.py > wip/horse-skills/proto/c40r_h3_out.txt
"""
import sys
import time
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

sys.path.insert(0, "wip/horse-skills/proto")
from c40r import CASES, BUDGETS, RUNS, SEED                                # noqa: E402


def main():
    d = H.load_data()
    print(f"# C40r H3: +1 Change Coupon vs +1 Level Down Ticket (fast engine, reset, when_stuck stop, {RUNS} horses)")
    print("set\thorse\ttraining\tB\ttickets\tbase full\tbase stuck\t+coupon: full gain\t+coupon: stuck drop\t"
          "+ticket always: full gain\t+ticket always: stuck drop\tbehind base full\tbehind base stuck\t"
          "+ticket behind: full gain\t+ticket behind: stuck drop\t+ticket behind: tickets used (base -> +1)")
    for wset, tr, name in CASES:
        t0 = time.time()
        h = H.get_horse(d, name)
        M = h.M(H.training_bonus(tr))
        wanted = H.WANTED_SETS[wset]
        bmax = max(BUDGETS[wset]) + 1
        plans = sorted({H.rule_plan(B + k, 1, wanted) for B in BUDGETS[wset] for k in (0, 1)})
        ev = lambda tk, **pol: F.Evaluator(h, M, max_budget=bmax, wanted=wanted, tickets=tk, **pol).plans(
            plans, RUNS, SEED, used=True)
        R = {(tk, pol): ev(tk, **({"ticket_behind": 0.0} if pol == "behind" else {}))
             for tk in (0, 1, 2, 3, 5, 6) for pol in ("always", "behind")}
        for B in BUDGETS[wset]:
            p, p1 = H.rule_plan(B, 1, wanted), H.rule_plan(B + 1, 1, wanted)
            for tk in (0, 2, 5):
                a, c, t, bb, bt = (R[(tk, "always")][p], R[(tk, "always")][p1], R[(tk + 1, "always")][p],
                                   R[(tk, "behind")][p], R[(tk + 1, "behind")][p])
                print(f"{wset}\t{name}\t{tr}\t{B}\t{tk}\t{100 * a['full'][B]:.2f}\t{100 * a['stuck']:.3f}\t"
                      f"{100 * (c['full'][B + 1] - a['full'][B]):.2f}\t{100 * (a['stuck'] - c['stuck']):.3f}\t"
                      f"{100 * (t['full'][B] - a['full'][B]):.2f}\t{100 * (a['stuck'] - t['stuck']):.3f}\t"
                      f"{100 * bb['full'][B]:.2f}\t{100 * bb['stuck']:.3f}\t"
                      f"{100 * (bt['full'][B] - bb['full'][B]):.2f}\t{100 * (bb['stuck'] - bt['stuck']):.3f}\t"
                      f"{bb['tickets_used']:.2f} -> {bt['tickets_used']:.2f}")
        print(f"# {name} {tr}: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
