"""C25r follow-up (2026-11-24): stuck share with the Selection Coupon (rule plan for B, fallback) vs the
no-coupon rule plan for B + k extra Change Coupons, k = the worth rounded up (from c25r_out.txt). 20,000 horses."""
import sys, math
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
rows = [l.rstrip("\n").split("\t") for l in open("wip/horse-skills/proto/c25r_out.txt") if l.startswith(("courser", "travel"))]
d = H.load_data()
print("set\thorse\ttraining\tB\tworth\tstuck: B + coupon\tstuck: B + k coupons\tfull: B + coupon (fallback)\tfull: B + k")
for r in rows:
    wset, name, tr, B, wf = r[0], r[1], r[2], int(r[3]), r[7]
    if wf.startswith(">") or float(wf) == 0:
        continue
    k = math.ceil(float(wf))
    h = H.get_horse(d, name); M = h.M(H.training_bonus(tr)); wanted = H.WANTED_SETS[wset]
    p1, p2 = H.rule_plan(B, 1, wanted), H.rule_plan(B + k, 1, wanted)
    ev = F.Evaluator(h, M, max_budget=B + k, wanted=wanted)
    a = ev.plans([p1], 20000, 2501, coupon="fallback")[p1]
    b = ev.plans([p2], 20000, 2501)[p2]
    print(f"{wset}\t{name}\t{tr}\t{B}\t{wf}\t{100 * a['stuck']:.2f}\t{100 * b['stuck']:.2f}\t{100 * a['full'][B]:.1f}\t{100 * b['full'][B + k]:.1f}")
