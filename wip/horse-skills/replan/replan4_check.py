"""Checks for replan4.py: (1) a re-plan that only continues the current plan reproduces the fixed play exactly;
(2) the fixed play's average exact chance matches the tool's value for the level-1 plan (different horses: within
noise). Usage: python3 -I replan4_check.py t8|doom|dine N"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replan4 as R

case, N = sys.argv[1], int(sys.argv[2])
s = dict(R.COMMON, **R.CASES[case])
S = R.Setup(s)
plan, chance = R.decide(S, s, 1, 0, s["coupons"], 0, s["seed"] * 1000 + 1, runs=s["first_runs"])
same, xs = 0, []
for i in range(N):
    hs = s["seed"] * 1_000_003 + i
    fx = R.play(S, s, plan, hs)
    xs.append(fx["chance"])
    # replay where each decision continues the current plan: same strategy and threshold, start at least the next
    # level, cap = what the plan may still spend
    def dec(lv, have, left, pts, sd):
        used_now = s["coupons"] - left
        st, sf, cap, T = cur["p"]
        newp = (st, max(sf, lv + 1), max(0, cap - (used_now - cur["base"])), T)
        cur["p"], cur["base"] = newp, used_now
        return newp, 0.0
    cur = {"p": plan, "base": 0}
    rp = R.play(S, s, plan, hs, replan_seed=1, decide_fn=dec)
    same += rp["chance"] == fx["chance"] and rp["skills"] == fx["skills"] and rp["points"] == fx["points"]
m = sum(xs) / N
se = math.sqrt(sum((x - m) ** 2 for x in xs) / (N - 1) / N)
print(f"{case}: level-1 plan {plan} tool {chance:.4f}; fixed play {m:.4f} (se {se:.4f}, z {(m - chance) / se:+.2f}); "
      f"'continue' replays identical {same}/{N}")
