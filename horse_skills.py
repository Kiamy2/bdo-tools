#!/usr/bin/env python3
"""horse_skills.py - Black Desert horse skill odds and leveling-strategy simulator (offline).

  python3 -I horse_skills.py --list
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7"                  # strategies, a/b/c
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --coupons 10 --tickets 4
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --sweep 0,10,20,40
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --odds --gear      # next level-up odds
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --check "Ruade=15.1844" "none=10.7826"

a/b/c columns: a = no boxes, b = Pearl horse gear OR Mount Brand Spell Stone (both are +10%), c = both.
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
    ap.add_argument("--tickets", type=int, default=0, help="Mount Level Down Tickets (used on level-ups that teach nothing)")
    ap.add_argument("--strategy", help="comma-separated subset (default all): "
                    + "; ".join(f"{k} = {v}" for k, v in H.STRATEGY_HELP.items()))
    ap.add_argument("--wanted", help="wanted skills, comma-separated (default: the travel set, see docs)")
    ap.add_argument("--reserve", type=int, default=5, help="coupons coursier/hard keep for level 30 (default 5)")
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

    budgets = [int(x) for x in a.sweep.split(",")] if a.sweep else [a.coupons]
    W = set(H.TRAVEL_SET if wanted is None else wanted) & set(horse.weights)
    print(head)
    print(f"# level {a.level} -> 30 | learned: {', '.join(map(show, learned)) or '-'} | tickets {a.tickets} | "
          f"{a.runs} runs | reserve {a.reserve} | wanted: {len(W)} skills, learnable: {len(horse.weights)}")
    print("# cells a/b/c = no boxes / gear or brand stone / both")
    print("strategy\tcoupons\tskills at 30\twanted at 30\tall wanted\tcoupons used")
    for budget in budgets:
        for strat in strategies:
            res = []
            for gear, brand in [(0, 0), (1, 0), (1, 1)]:
                res.append(H.simulate(horse, horse.M(bonus, gear, brand), strat, budget, a.tickets, a.level, learned,
                                      wanted, fodder, a.point_bonus, a.points, a.runs, a.seed,
                                      reserve=a.reserve))
            cell = lambda k, f: "/".join(f.format(r[k]) for r in res)
            cp = "-" if strat == "natural" else ("unlimited" if strat == "ideal" else str(budget))
            used = "-" if strat in ("natural", "ideal") else cell("coupons_used", "{:.0f}")
            allw = "/".join(f"{100 * r['all_wanted']:.0f}%" for r in res)
            print(f"{strat}\t{cp}\t{cell('skills', '{:.1f}')}\t{cell('wanted', '{:.1f}')}\t{allw}\t{used}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
