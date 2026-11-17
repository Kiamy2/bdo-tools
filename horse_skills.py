#!/usr/bin/env python3
"""horse_skills.py - Black Desert horse skill odds and leveling-strategy simulator (offline).

  python3 -I horse_skills.py --list
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7"                  # strategies, a/b/c
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --coupons 10 --tickets 4
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --sweep 0,10,20,40
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --odds --gear      # next level-up odds
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --check "Ruade=15.1844" "none=10.7826"

a/b/c columns: a = no learn-chance boost, b = Pearl horse gear set OR Mount Brand Spell Stone (both are +10%), c = both.
Exit codes: 0 ok; 2 bad input (unknown horse, skill or Training level); 1 --check found a mismatch.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # repo root (works with python3 -I)
from bdo import horses as H  # noqa: E402


def names_list(text, resolve):
    return [resolve(s) for s in text.split(",") if s.strip()] if text else []


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="BDO horse skill odds and leveling-strategy simulator")
    ap.add_argument("horse", nargs="?", help="horse name from the data file (see --list)")
    ap.add_argument("--list", action="store_true", help="list the horses in the data file")
    ap.add_argument("--horse-file", metavar="CSV", help="use your own simulator reading instead (see docs/horse_skills.md)")
    ap.add_argument("--training", help="your Training level: 'Artisan 7', 'Master 20', 'Gourou 5'... or a bonus like 21.7")
    ap.add_argument("--gear", action="store_true", help="Pearl horse gear (4 pieces) worn (--odds/--check)")
    ap.add_argument("--brand", action="store_true", help="Mount Brand Spell Stone used (--odds/--check)")
    ap.add_argument("--learned", help="skills already learned, comma-separated (English or French)")
    ap.add_argument("--odds", action="store_true", help="print the next level-up's odds, like the in-game simulator")
    ap.add_argument("--check", nargs="+", metavar="SKILL=PCT", help="compare odds read in the in-game simulator with the model "
                    "(use 'none' for the no-skill line)")
    ap.add_argument("--level", type=int, default=1, help="current horse level (default 1)")
    ap.add_argument("--coupons", type=int, default=30, help="Mount Skill Change Coupons available (default 30)")
    ap.add_argument("--sweep", metavar="N,N,..", help="run several coupon budgets instead of --coupons")
    ap.add_argument("--target", metavar="PCT,PCT,..", help="instead of a coupon budget: coupons needed to end "
                    "with every wanted skill in PCT%% of runs, e.g. 50,80,90")
    ap.add_argument("--optimize", type=int, metavar="MAX_COUPONS",
                    help="search the best plan (strategy, level to start swapping, coupons to keep) for every "
                    "budget from 0 to MAX_COUPONS, for the full set and for the most wanted skills")
    ap.add_argument("--tickets", type=int, default=0, help="Mount Level Down Tickets (used on level-ups that teach nothing)")
    ap.add_argument("--strategy", help="comma-separated subset (default all): "
                    + "; ".join(f"{k} = {v}" for k, v in H.STRATEGY_HELP.items()))
    ap.add_argument("--wanted", help="wanted skills, comma-separated (default: the travel set, see docs)")
    ap.add_argument("--reserve", type=int, default=5, help="coupons coursier/once/hard keep for level 30 (default 5)")
    ap.add_argument("--swap-from", type=int, default=1, metavar="LEVEL",
                    help="coursier/once/hard only start swapping once the horse reaches this level (default 1)")
    ap.add_argument("--fodder", help="skills the 'coursier' strategy swaps out (default: Hind Kick,Fore Chop)")
    ap.add_argument("--points", type=int, default=0, help="Skill Change Points the horse already has (default 0)")
    ap.add_argument("--point-bonus", type=float, default=0.25, help="desired-skill weight bonus per point (default 0.25)")
    ap.add_argument("--runs", type=int, default=5000, help="simulated levelings per cell (default 5000)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lang", default="en", choices=["en", "fr"], help="skill names in output")
    a = ap.parse_args()

    try:
        data = H.load_data()
        resolve = H.skill_resolver(data)
        if a.list:
            print("horse\ttier\tlearnable\tdate\tsource\tno-skill weight")
            for name in H.horse_names(data):
                h = data["horses"][name]
                print(f"{name}\t{h['tier']}\t{len(h['weights'])}\t{h['date']}\t{h['source']}\t{h['no_skill_weight_note']}")
            return 0
        if a.horse_file:
            horse = H.horse_from_sim_file(a.horse_file, resolve)
        elif a.horse:
            horse = H.get_horse(data, a.horse)
        else:
            ap.error("give a horse name (see --list) or --horse-file")
        if a.training is None:
            ap.error("--training is required, e.g. --training 'Artisan 7'")
        bonus = H.training_bonus(a.training)
        learned = names_list(a.learned, resolve)
        wanted = names_list(a.wanted, resolve) if a.wanted else None
        fodder = names_list(a.fodder, resolve) if a.fodder else None
        strategies = [s.strip() for s in a.strategy.split(",")] if a.strategy else H.STRATEGIES
        for s in strategies:
            if s not in H.STRATEGIES:
                raise H.DataError(f"unknown strategy {s!r}")
        try:
            targets = [float(x) for x in a.target.split(",")] if a.target else []
        except ValueError:
            raise H.DataError(f"--target takes percentages like 50,80,90, not {a.target!r}")
        if any(not 0 < x <= 100 for x in targets):
            raise H.DataError("--target percentages must be above 0 and at most 100")
    except H.DataError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    fr = data["skills_fr"]
    show = (lambda s: fr.get(s) or s) if a.lang == "fr" else (lambda s: s)
    M = horse.M(bonus, a.gear, a.brand)
    head = f"# {horse.name} (T{horse.tier})" if horse.tier and f"T{horse.tier}" not in horse.name else f"# {horse.name}"
    head += f" | Training bonus {bonus:g}%" + (" + gear" if a.gear else "") + (" + brand" if a.brand else "")
    head += f" | data {horse.date or 'undated'}: {horse.source}"

    if a.odds or a.check:
        p, none = horse.odds(M, set(learned) | set(horse.born_with))
        if a.odds:
            print(head)
            print("skill\tchance")
            print(f"none\t{100 * none:.4f}%")
            for s in sorted(p, key=lambda s: -p[s]):
                print(f"{show(s)}\t{100 * p[s]:.4f}%")
        if a.check:
            print("skill\tmodel\tobserved\tdiff\tnote")
            bad = 0
            for item in a.check:
                name, _, val = item.rpartition("=")
                try:
                    obs = float(val.strip().rstrip("%"))
                    key = "none" if name.strip().lower() in ("none", "compétence non apprise") else resolve(name)
                except (ValueError, H.DataError) as e:
                    print(f"ERROR: {item!r}: {e}", file=sys.stderr)
                    return 2
                model = 100 * (none if key == "none" else p.get(key, 0.0))
                # tolerance: the data's weights are rounded to 0.01 (bdolytics), the game shows 4 decimals
                scale = (sum(p.values()) / sum(horse.weights[s] for s in p)) if p else 0
                n = len(p) if key == "none" else 1
                ok = abs(model - obs) <= 100 * scale * 0.0055 * n + 0.002
                bad += not ok
                print(f"{show(key) if key != 'none' else 'none'}\t{model:.4f}\t{obs:.4f}\t{model - obs:+.4f}\t{'' if ok else 'MISMATCH'}")
            if bad:
                print(f"# {bad} mismatch(es): the data may be outdated, or the reading's settings differ", file=sys.stderr)
                return 1
        return 0

    if a.optimize is not None:
        return optimize_report(a, horse, bonus, learned, wanted, fodder, head)
    budgets = [int(x) for x in a.sweep.split(",")] if a.sweep else [a.coupons]
    W = set(H.TRAVEL_SET if wanted is None else wanted) & set(horse.weights)
    print(head)
    print(f"# level {a.level} -> 30 | learned: {', '.join(map(show, learned)) or '-'} | tickets {a.tickets} | "
          f"{a.runs} runs | reserve {a.reserve} | swaps from level {a.swap_from} | wanted: {len(W)} skills, learnable: {len(horse.weights)}")
    print("# cells a/b/c = no boost / gear set or brand stone / both")
    if targets:
        print("# coupons needed to end with every wanted skill in the given share of runs (+/-1 coupon; >150 = not reached)")
        print("strategy\t" + "\t".join(f"for {t:g}%" for t in targets))
        for strat in strategies:
            if strat in ("natural", "ideal"):
                continue
            caches = [{} for _ in range(3)]
            cols = []
            for t in targets:
                vals = []
                for i, (gear, brand) in enumerate([(0, 0), (1, 0), (1, 1)]):
                    n = H.coupons_needed(horse, horse.M(bonus, gear, brand), strat, t / 100, cache=caches[i],
                                         tickets=a.tickets, start_level=a.level, learned=learned, wanted=wanted,
                                         fodder=fodder, point_bonus=a.point_bonus, points=a.points, runs=a.runs,
                                         seed=a.seed, reserve=a.reserve, swap_from=a.swap_from)
                    vals.append(">150" if n is None else str(n))
                cols.append("/".join(vals))
            print(f"{strat}\t" + "\t".join(cols))
        return 0
    print("strategy\tcoupons\tskills at 30\twanted at 30\tall wanted\tcoupons used")
    for budget in budgets:
        for strat in strategies:
            res = []
            for gear, brand in [(0, 0), (1, 0), (1, 1)]:
                res.append(H.simulate(horse, horse.M(bonus, gear, brand), strat, budget, a.tickets, a.level, learned,
                                      wanted, fodder, a.point_bonus, a.points, a.runs, a.seed,
                                      reserve=a.reserve, swap_from=a.swap_from))
            cell = lambda k, f: "/".join(f.format(r[k]) for r in res)
            cp = "-" if strat == "natural" else ("unlimited" if strat == "ideal" else str(budget))
            used = "-" if strat in ("natural", "ideal") else cell("coupons_used", "{:.0f}")
            allw = "/".join(f"{100 * r['all_wanted']:.0f}%" for r in res)
            print(f"{strat}\t{cp}\t{cell('skills', '{:.1f}')}\t{cell('wanted', '{:.1f}')}\t{allw}\t{used}")
    return 0


def optimize_report(a, horse, bonus, learned, wanted, fodder, head):
    import time
    M = horse.M(bonus, a.gear, a.brand)
    kw = dict(tickets=a.tickets, start_level=a.level, learned=learned, wanted=wanted, fodder=fodder,
              point_bonus=a.point_bonus, points=a.points)
    t0 = time.time()
    res = H.optimize(horse, M, a.optimize, seed=a.seed,
                     progress=lambda i, n: i % 100 == 0 and print(f"# stage 1: {i}/{n} plans", file=sys.stderr), **kw)
    nw = next(iter(res.values()))["wanted_total"]
    print(head)
    print(f"# level {a.level} -> 30 | learned: {', '.join(learned) or '-'} | tickets {a.tickets} | "
          f"wanted: {nw} skills | {len(res)} plans in stage 2 | {time.time() - t0:.0f}s")
    print("# For each budget: the plans tied with the best (within 1 point for the full set, 0.05 skill for the")
    print("# average), as spans: 'from lvl' = level to start swapping, 'keep' = coupons kept for the level-30 cleanup.")
    print("# The spans cover the tied plans; not every combination inside a span is tied.")
    print("coupons\tfull set: chance\ttied plans\tmost wanted: avg\ttied plans\tat30: chance, avg")
    at30 = res[("at30", 1, 0)]
    best_full = []
    for B in range(a.optimize + 1):
        tf = H.tied_plans(res, B, "full", 0.01)
        tw = H.tied_plans(res, B, "wanted", 0.05)
        best_full.append(res[tf[0]]["full"][B])
        print(f"{B}\t{100 * res[tf[0]]['full'][B]:.1f}%\t{H.describe_plans(tf, B)}\t"
              f"{res[tw[0]]['wanted'][B]:.2f}\t{H.describe_plans(tw, B)}\t"
              f"{100 * at30['full'][B]:.1f}%, {at30['wanted'][B]:.2f}")
    for t in (0.5, 0.8, 0.9, 0.95):
        b = next((B for B, x in enumerate(best_full) if x >= t), None)
        b30 = next((B for B, x in enumerate(at30["full"]) if x >= t), None)
        print(f"# coupons for a {t:.0%} chance of the full set: {b if b is not None else '> max'} with the best plan, "
              f"{b30 if b30 is not None else '> max'} with at30")
    return 0

if __name__ == "__main__":
    sys.exit(main())
