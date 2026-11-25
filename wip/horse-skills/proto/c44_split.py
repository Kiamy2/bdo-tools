"""C44 (2026-11-25): with a fixed number of items (Change Coupons + Level Down Tickets, the same price in Pearls when
bought singly), which split gives the best full-set chance?
Cases: as c40r.py (courser set: T8 Types 1, 2, 4; travel set: Mythical Diné, Doom, Arduanatt; Beginner 1 / Skilled 1 /
Artisan 7; no boosts, from level 1). For every split: B coupons, t tickets (t = 0..25, B = 0..40), the general rule's
plan for B coupons, tickets on every level-up that teaches nothing (the tool's default). Fast engine (exact cleanup,
points reset, when_stuck stop), 10,000 horses, the same horses for every split (seed 4401).
One line per case x B x t; resumable (cases already in the output file are skipped).
Usage (repo root): python3 -I wip/horse-skills/proto/c44_split.py wip/horse-skills/proto/c44_split_out.txt
"""
import os
import sys
import time
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F

RUNS, SEED, BMAX, TMAX = 10000, 4401, 40, 25
TRAINING = ("Beginner 1", "Skilled 1", "Artisan 7")
CASES = ([("courser", t, h) for h in ("T8 Type 1", "T8 Type 2", "T8 Type 4") for t in TRAINING]
         + [("travel", t, h) for h in ("Mythical Diné", "Mythical Doom", "Mythical Arduanatt") for t in TRAINING])
HEAD = "set\thorse\ttraining\tB\ttickets\tfull set\tstuck\tcoupons used\ttickets used"


def main(path):
    done = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if line.startswith("# done "):
                done.add(line[7:].strip())
    out = open(path, "a", encoding="utf-8")
    if not done:
        out.write(f"# C44 split: {RUNS} horses, seed {SEED}, B 0-{BMAX}, tickets 0-{TMAX}, the rule's plan, tickets "
                  "always\n" + HEAD + "\n")
    d = H.load_data()
    for wset, tr, name in CASES:
        key = f"{wset}|{name}|{tr}"
        if key in done:
            continue
        t0 = time.time()
        h = H.get_horse(d, name)
        M = h.M(H.training_bonus(tr))
        wanted = H.WANTED_SETS[wset]
        plans = sorted({H.rule_plan(B, 1, wanted) for B in range(BMAX + 1)})
        lines = []
        for t in range(TMAX + 1):
            r = F.Evaluator(h, M, max_budget=BMAX, wanted=wanted, tickets=t).plans(plans, RUNS, SEED, used=True)
            for B in range(BMAX + 1):
                x = r[H.rule_plan(B, 1, wanted)]
                lines.append(f"{wset}\t{name}\t{tr}\t{B}\t{t}\t{100 * x['full'][B]:.3f}\t{100 * x['stuck']:.3f}\t"
                             f"{x['used'][B]:.3f}\t{x['tickets_used']:.3f}")
        out.write("\n".join(lines) + f"\n# done {key}\n")
        out.flush()
        print(f"{key}: {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
