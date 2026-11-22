"""P4 frontier prototype (2026-11-22): three criteria per plan, and how they agree.

For every plan of horses_fast.search_grid (spending caps up to N), with N coupons in total:
  full  = chance of the full set within N coupons (exact cleanup),
  used  = coupons used on average with N available (exact cleanup; stuck horses stop, capped ones count N),
  stuck = chance that the horse reaches level 30 with fewer learned skills than learnable wanted skills
          (no coupon can fix it: a coupon never changes the skill count; the Selection Coupon needs an unwanted
          skill), from the simulated horses at level 30.
Stage 1: 1000 horses per plan; the plans not dominated on the three criteria (with a noise tolerance) are rechecked
with 20,000 fresh horses, and the frontier is recomputed on those values.

Usage: python3 -I wip/horse-skills/proto/p4f.py   (from the repo root; prints the cases below)
"""
import sys, time
sys.path.insert(0, ".")
import numpy as np
from bdo import horses as H, horses_fast as F

T6L = ("Hind Kick,Fore Chop,Drift,Start Accel,High Jump,Quick Stop,Charge,Quick Back,Streak Leap,Roar,Caution,"
       "Quick Ride,S: Hind Kick,S: Fore Chop,S: Sideways").split(",")


def stuck_share(ev, plans, runs, seed):
    """Per plan: the share of horses reaching level 30 with fewer learned skills than learnable wanted skills."""
    w, n, W, M = ev.args
    lmask, wmask, fod, cyc, order, rare = ev.masks
    out = {}
    for p in plans:
        st, lv, cap, T = p
        S, _, _ = F._many30(runs, seed, w, n, W, M, F.CODES[st], lv, 0 if st == "at30" else cap, ev.tickets,
                            ev.start_level, lmask, wmask, fod, cyc, order, rare, ev.pb, ev.points, ev.max_level, T,
                            False)
        out[p] = float((F._popcounts(S) < ev.n_wanted).mean())
    return out


def criteria(ev, plans, N, runs, seed):
    r = ev.plans(plans, runs, seed, used=True, at_most=True)
    st = stuck_share(ev, plans, runs, seed)
    for p in plans:
        r[p]["stuck"] = st[p]
    return r


def dominated(a, b, tol=(0.0, 0.0, 0.0)):
    """b beats a on all three (full higher, used lower, stuck lower), by more than tol on at least one, and not
    worse than a on any."""
    fa, ua, sa = a
    fb, ub, sb = b
    if fb < fa or ub > ua or sb > sa:
        return False
    return fb > fa + tol[0] or ub < ua - tol[1] or sb < sa - tol[2]


def eps_dominated(a, b, eps):
    """b beats a within noise: no worse than a by more than eps on any criterion, and better by more than eps on one."""
    fa, ua, sa = a
    fb, ub, sb = b
    if fb < fa - eps[0] or ub > ua + eps[1] or sb > sa + eps[2]:
        return False
    return fb > fa + eps[0] or ub < ua - eps[1] or sb < sa - eps[2]


EPS = (0.003, 0.03, 0.003)      # 0.3 points, 0.03 coupons, 0.3 points: about the noise at 20,000 horses


def eps_frontier(r, N):
    pts = {p: (r[p]["full"][N], r[p]["used"][N], r[p]["stuck"]) for p in r}
    return [p for p in pts if not any(eps_dominated(pts[p], pts[q], EPS) for q in pts if q != p)]


def frontier(r, N, tol=(0.0, 0.0, 0.0)):
    pts = {p: (r[p]["full"][N], r[p]["used"][N], r[p]["stuck"]) for p in r}
    return [p for p in pts if not any(dominated(pts[p], pts[q], tol) for q in pts if q != p)]


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def thin(r, plans, N, n_learned, level):
    """One plan per effective plan, then drop a plan whose three values are within noise of a kept one (0.3 points,
    0.03 coupons, 0.3 points), keeping the higher full-set chance."""
    seen, out = set(), []
    for p in sorted(plans, key=lambda p: -r[p]["full"][N]):
        e = H.effective_plan(p, n_learned, level)
        v = (r[p]["full"][N], r[p]["used"][N], r[p]["stuck"])
        if e in seen or any(abs(v[0] - u[0]) < 0.003 and abs(v[1] - u[1]) < 0.03 and abs(v[2] - u[2]) < 0.003
                            for u in (x[1] for x in out)):
            continue
        seen.add(e)
        out.append((p, v))
    return [p for p, _ in out]


def run_case(label, horse, M, N, start_level=1, learned=(), wanted=None, seed=1):
    t0 = time.time()
    kw = dict(start_level=start_level, learned=list(learned), wanted=wanted)
    ev = F.Evaluator(horse, M, max_budget=N, **kw)
    plans = F.search_grid(start_level, N)
    s1 = criteria(ev, plans, N, 1000, seed)
    f = np.array([s1[p]["full"][N] for p in plans])
    u = np.array([s1[p]["used"][N] for p in plans])
    s = np.array([s1[p]["stuck"] for p in plans])
    nl = len(set(learned) & set(horse.weights))
    print(f"\n## {label}: N = {N} coupons, {len(plans)} plans, wanted learnable {ev.n_wanted}")
    print(f"# stage 1 (1000 horses): rank correlations over all plans: full vs -used {spearman(f, -u):+.2f}, "
          f"full vs -stuck {spearman(f, -s):+.2f}, -used vs -stuck {spearman(-u, -s):+.2f}")
    print(f"# stage 1 ranges: full {100*f.min():.1f}-{100*f.max():.1f}%, used {u.min():.2f}-{u.max():.2f}, "
          f"stuck {100*s.min():.1f}-{100*s.max():.1f}%")
    cand = frontier(s1, N, (0.01, 0.1, 0.01))            # lenient at 1000 horses: keep near-frontier plans
    cand = sorted(cand, key=lambda p: -s1[p]["full"][N])[:60] + [("at30", 1, 0, 0)]
    cand = list(dict.fromkeys(cand))
    r = criteria(ev, cand, N, 20000, seed + 2000)
    fr = thin(r, eps_frontier(r, N), N, nl, start_level)
    rr = [r[p] for p in cand]
    print(f"# {len(cand)} near-frontier plans rechecked with 20,000 fresh horses; frontier {len(frontier(r, N))} plans, "
          f"{len(fr)} within noise (EPS) and after merging near-duplicates; {time.time() - t0:.0f}s")
    print(f"# rechecked, over those plans: full vs -used {spearman([x['full'][N] for x in rr], [-x['used'][N] for x in rr]):+.2f}, "
          f"full vs -stuck {spearman([x['full'][N] for x in rr], [-x['stuck'] for x in rr]):+.2f}")
    best = {"chance": max(fr, key=lambda p: r[p]["full"][N]), "coupons": min(fr, key=lambda p: r[p]["used"][N]),
            "safe": min(fr, key=lambda p: (r[p]["stuck"], -r[p]["full"][N]))}
    cols = [B for B in (1, 2, 3, 5, 10) if B < N]
    # average coupons of the horses that get the full set within N: from P(total <= B), B = 0..N
    succ = lambda am: sum(B * (am[B] - (am[B - 1] if B else 0)) for B in range(N + 1)) / am[N] if am[N] else float("nan")
    impossible = nl >= ev.n_wanted                      # already holds enough skills: stuck can't happen
    stk = lambda x: "0%" if impossible else (f"<{300 / 20000:.2f}%" if x == 0 else f"{100 * x:.1f}%")
    # '*' on the best value of each criterion column (within EPS of the best)
    bf, bu, bs = (max(r[p]["full"][N] for p in fr), min(r[p]["used"][N] for p in fr), min(r[p]["stuck"] for p in fr))
    star = lambda ok: "*" if ok and len(fr) > 1 else ""
    if len(fr) == 1:
        print("# One plan is the best on every criterion.")
    print(f"plan\tfull set within {N}\tstuck\tran out\tcoupons: avg (all)\tavg (successes)\tmedian\t"
          + "\t".join(f"at most {B}" for B in cols) + "\tpick")
    q = lambda am, x: next((str(B) for B, v in enumerate(am) if v >= x - 1e-9), f">{N}")
    for p in fr:
        x = r[p]
        am = x["at_most"]
        tags = ",".join(k for k, v in best.items() if v == p)
        print(f"{H.plan_name(p, None, nl, start_level)}\t{100*x['full'][N]:.1f}%{star(x['full'][N] >= bf - EPS[0])}\t"
              f"{stk(x['stuck'])}{star(x['stuck'] <= bs + EPS[2])}\t{100*(1 - x['full'][N] - x['stuck']):.1f}%\t"
              f"{x['used'][N]:.2f}{star(x['used'][N] <= bu + EPS[1])}\t{succ(am):.2f}\t{q(am, 0.5)}\t"
              + "\t".join(f"{100*am[B]:.1f}%" for B in cols) + f"\t{tags}")
    a = r[("at30", 1, 0, 0)]
    if ("at30", 1, 0, 0) not in fr:
        print(f"(at30, not on the frontier: {100*a['full'][N]:.1f}% / stuck {100*a['stuck']:.1f}% / {a['used'][N]:.2f})")
    return r, fr


if __name__ == "__main__":
    d = H.load_data()
    h6 = H.get_horse(d, "T8 Type 6")
    run_case("T8 Type 6, Artisan 9, gear, level 19, 15 learned (live test 1), courser", h6, h6.M(23.1, True), 5,
             19, T6L, H.COURSER_SET)
    run_case("same, N = 10", h6, h6.M(23.1, True), 10, 19, T6L, H.COURSER_SET)
    h2 = H.get_horse(d, "T8 Type 2")
    run_case("T8 Type 2, Artisan 7, level 1, courser", h2, h2.M(21.7), 20, 1, (), H.COURSER_SET)
    h1 = H.get_horse(d, "T8 example (bdolytics icon horse_71)")
    run_case("T8 example, Skilled 1, level 1, travel (hard)", h1, h1.M(H.training_bonus("Skilled 1")), 20, 1, (),
             H.TRAVEL_SET)
