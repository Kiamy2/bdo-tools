#!/usr/bin/env python3
"""horse_skills.py - Black Desert horse skill odds and leveling-strategy simulator (offline).

  python3 -I horse_skills.py --list
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7"                  # strategies, a/b/c
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --coupons 10 --tickets 4
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --sweep 0,10,20,40
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --odds --gear      # next level-up odds
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --check "Ruade=15.1844" "none=10.7826"
  python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --optimize 30         # best plan per budget

--optimize uses the fast engine (bdo/horses_fast.py) when numba is installed (pip install -r
requirements-optional.txt): every plan is tried and the level-30 cleanup is computed exactly. Without numba it
falls back to plain Python (a grid of plans, slower and noisier).

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
    ap.add_argument("--innate", metavar="SKILLS", help="extra innate skills of a special horse, comma-separated: "
                    "the horse's weights without them, same 'no skill' weight (check with --check and a reading)")
    ap.add_argument("--training", help="your Training level: 'Artisan 7', 'Master 20', 'Gourou 5'... or a bonus like 21.7")
    ap.add_argument("--gear", action="store_true", help="Pearl horse gear (4 pieces) worn (every computation: +0.10)")
    ap.add_argument("--brand", action="store_true", help="Mount Brand Spell Stone used (every computation: +0.10)")
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
    ap.add_argument("--wanted", help="wanted skills, comma-separated, or a named set: 'courser' (what a T8 needs for "
                    "courser training: Charge, Drift, Sprint, Instant Accel, Sideways, S: Instant Accel, S: Sideways) "
                    "or 'travel' (an example of a finished set for a T10, see docs). Default: courser for a T8, "
                    "travel otherwise")
    ap.add_argument("--reserve", type=int, default=5, help="coupons the swapping strategies keep for level 30 (default 5)")
    ap.add_argument("--swap-from", type=int, default=1, metavar="LEVEL",
                    help="the swapping strategies only start once the horse reaches this level (default 1)")
    ap.add_argument("--switch-at", type=int, default=H.DEFAULT_SWITCH_AT, metavar="T",
                    help="coursier_switch: learned skills (innate ones don't count) at which it goes from coursier to "
                    f"coursier_v2 swaps (default {H.DEFAULT_SWITCH_AT})")
    ap.add_argument("--fodder", help="skills the 'coursier' strategy swaps out, in that order (default: Fore Chop,"
                    "Hind Kick)")
    ap.add_argument("--points", type=int, default=0, help="Skill Change Points the horse already has (default 0)")
    ap.add_argument("--point-bonus", type=float, default=0.25, help="desired-skill weight bonus per point (default 0.25)")
    ap.add_argument("--runs", type=int, default=5000, help="simulated levelings per cell (default 5000)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--engine", default="auto", choices=["auto", "python", "numba"],
                    help="--optimize engine: numba (fast, exact cleanup; needs numba), python, or auto (default: "
                    "numba if installed)")
    ap.add_argument("--selection-coupon", choices=["planned", "fallback"],
                    help="--optimize with one Mount Skill Selection Coupon, used at the very end on the last missing "
                    "skill (the horse needs an unwanted skill to change). planned: you'll use it for sure; every Change "
                    "Coupon then aims at the second rarest missing skill and keeps the rarest for it (a bit better, "
                    "but only if you do use it). fallback: a safety net; plans as without it, plus your chance if you "
                    "decide at level 30 to use it (from then on, the cleanup keeps the rarest for it)")
    ap.add_argument("--low-memory", action="store_true",
                    help="--optimize, fast engine: keep the level-30 values as 16-bit numbers (less memory, results "
                    "within about 0.001 points; speed about the same)")
    ap.add_argument("--always-best", action="store_true",
                    help="--optimize: suggest the best plan found for every budget, even when the general rule's "
                    "plan is within 1 point of it (by default the rule's plan is suggested then: the best of many "
                    "near-tied plans is partly luck, and the rule changes smoothly with the budget)")
    ap.add_argument("--coupons-used", nargs="?", const="all", metavar="N,N,..",
                    help="with --optimize: for the suggested plans of these budgets (default all), the chance of the "
                         "full set with at most B coupons in total for each B, and the spread of coupons used")
    ap.add_argument("--lang", default="en", choices=["en", "fr"], help="skill names in output")
    a = ap.parse_args()

    try:
        data = H.load_data()
        resolve = H.skill_resolver(data)
        if a.list:
            print("horse\ttier\tlearnable\tdate\tsource\tno-skill weight")
            for name in H.horse_names(data):
                h = data["horses"][name]
                also = f" (also {', '.join(h['aliases'])})" if h.get("aliases") else ""
                print(f"{name}{also}\t{h['tier']}\t{len(h['weights'])}\t{h['date']}\t{h['source']}\t"
                      f"{h['no_skill_weight_note']}")
            return 0
        if a.horse_file:
            horse = H.horse_from_sim_file(a.horse_file, resolve)
        elif a.horse:
            horse = H.get_horse(data, a.horse)
        else:
            ap.error("give a horse name (see --list) or --horse-file")
        if a.innate:
            horse = horse.with_innate(names_list(a.innate, resolve))
        if a.training is None:
            ap.error("--training is required, e.g. --training 'Artisan 7'")
        bonus = H.training_bonus(a.training)
        learned = names_list(a.learned, resolve)
        for x in [x for x in learned if x not in horse.weights]:
            why = ("innate for this horse: innate skills are not learned skills (in-game count = learned + innate)"
                   if x in horse.born_with else "not learnable by this horse")
            print(f"# note: ignoring {x!r} in --learned: {why}", file=sys.stderr)
        learned = [x for x in dict.fromkeys(learned) if x in horse.weights]
        wset = (a.wanted or H.default_wanted_set(horse)).strip().lower()
        wanted = list(H.WANTED_SETS[wset]) if wset in H.WANTED_SETS else names_list(a.wanted, resolve)
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
        if a.coupons_used is not None:
            if a.optimize is None:
                raise H.DataError("--coupons-used works with --optimize")
            try:
                used_budgets = (list(range(1, a.optimize + 1)) if a.coupons_used == "all"
                                else sorted({int(x) for x in a.coupons_used.split(",")}))
            except ValueError:
                raise H.DataError(f"--coupons-used takes coupon budgets like 2,3,4, not {a.coupons_used!r}")
            if any(not 1 <= x <= a.optimize for x in used_budgets):
                raise H.DataError(f"--coupons-used budgets must be from 1 to the --optimize maximum ({a.optimize})")
            a.used_budgets = used_budgets
    except H.DataError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    fr = data["skills_fr"]
    show = (lambda s: fr.get(s) or s) if a.lang == "fr" else (lambda s: s)
    M = horse.M(bonus, a.gear, a.brand)
    typed = H.typed_name(data, a.horse) if a.horse and not a.horse_file else horse.name
    base, plus, extra = horse.name.partition(" + innate ")
    name = horse.name if typed == base else f"{typed} (an alias of {base}: the same data)" + (plus + extra if plus else "")
    head = f"# {name} (T{horse.tier})" if horse.tier and f"T{horse.tier}" not in name else f"# {name}"
    head += f" | Training bonus {bonus:g}%" + (" + gear" if a.gear else "") + (" + brand" if a.brand else "")
    head += f" | data {horse.date or 'undated'}: {horse.source}"
    head += f"\n# wanted: {wset + ' set' if wset in H.WANTED_SETS else 'your list'}"
    if not a.wanted:
        head += f" (the default for a T{horse.tier or '?'}; --wanted courser / travel / your own list)"
    sure = H.sure_hits(horse, learned, wanted)
    if sure:
        head += (f"\n# every skill left to learn is wanted ({', '.join(map(show, sure))}): any swap is a sure hit; what"
                 "\n# matters is which skill you give up (level-ups may teach it back)")
    inn = horse.born_with
    a.learned_text = (f"learned: {len(learned)}" + (f" + {len(inn)} innate ({', '.join(map(show, inn))}) = "
                      f"{len(learned) + len(inn)} in game" if inn else "") + f": {', '.join(map(show, learned)) or '-'}")

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
        return optimize_report(a, horse, bonus, learned, wanted, fodder, head, show)
    if a.selection_coupon or a.always_best:
        print(f"ERROR: {'--selection-coupon' if a.selection_coupon else '--always-best'} works with --optimize",
              file=sys.stderr)
        return 2
    budgets = [int(x) for x in a.sweep.split(",")] if a.sweep else [a.coupons]
    W = set(H.TRAVEL_SET if wanted is None else wanted) & set(horse.weights)
    print(head)
    print(f"# level {a.level} -> 30 | {a.learned_text} | tickets {a.tickets} | "
          f"{a.runs} runs | reserve {a.reserve} | swaps from level {a.swap_from} | switch at {a.switch_at} learned skills | "
          f"wanted: {len(W)} skills, learnable: {len(horse.weights)}")
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
                                         seed=a.seed, reserve=a.reserve, swap_from=a.swap_from,
                                         switch_at=a.switch_at)
                    vals.append(">150" if n is None else str(n))
                cols.append("/".join(vals))
            print(f"{strat}\t" + "\t".join(cols))
        return 0
    print("# <=1 missing: chance of missing at most 1 wanted skill; worst 5%: wanted skills the worst 5% of runs miss")
    print("strategy\tcoupons\tskills at 30\twanted at 30\tall wanted\tcoupons used\t<=1 missing\tworst 5%")
    for budget in budgets:
        for strat in strategies:
            res = []
            for gear, brand in [(0, 0), (1, 0), (1, 1)]:
                res.append(H.simulate(horse, horse.M(bonus, gear, brand), strat, budget, a.tickets, a.level, learned,
                                      wanted, fodder, a.point_bonus, a.points, a.runs, a.seed,
                                      reserve=a.reserve, swap_from=a.swap_from, switch_at=a.switch_at))
            cell = lambda k, f: "/".join(f.format(r[k]) for r in res)
            cp = "-" if strat == "natural" else ("unlimited" if strat == "ideal" else str(budget))
            used = "-" if strat in ("natural", "ideal") else cell("coupons_used", "{:.0f}")
            allw = "/".join(f"{100 * r['all_wanted']:.0f}%" for r in res)
            le1 = "/".join(f"{100 * r['missing_le1']:.0f}%" for r in res)
            print(f"{strat}\t{cp}\t{cell('skills', '{:.1f}')}\t{cell('wanted', '{:.1f}')}\t{allw}\t{used}\t{le1}\t"
                  f"{cell('worst5_missing', '{}')}")
    return 0


def optimize_report(a, horse, bonus, learned, wanted, fodder, head, show=lambda s: s):
    import time
    from bdo import horses_fast as HF
    M = horse.M(bonus, a.gear, a.brand)
    kw = dict(tickets=a.tickets, start_level=a.level, learned=learned, wanted=wanted, fodder=fodder,
              point_bonus=a.point_bonus, points=a.points)
    engine = a.engine
    if engine == "auto":
        engine = "numba" if HF.available() else "python"
        if engine == "python":
            print("# numba not installed: plain-Python search (slower, noisier); "
                  "pip install -r requirements-optional.txt for the fast engine", file=sys.stderr)
    if engine == "numba" and not HF.available():
        print("ERROR: --engine numba needs numba (pip install -r requirements-optional.txt)", file=sys.stderr)
        return 2
    progress = lambda lab, i, n: (i % 500 == 0 or i == n) and print(f"# {lab}: {i}/{n} plans", file=sys.stderr)
    t0 = time.time()
    planned = "planned" if a.selection_coupon == "planned" else None

    def evaluate(plans, coupon=None, **override):
        """The given plans again, on the same horses as the final check (for the extra columns)."""
        k = dict(kw, **override)
        if engine == "numba":
            ev = HF.Evaluator(horse, M, max_budget=a.optimize, low_memory=a.low_memory, **k)
            return ev.plans(sorted(set(plans)), 4000, a.seed + 1000, tails=True, coupon=coupon)
        return {p: H.simulate_plan(horse, M, p[0], p[1], p[2], a.optimize, runs=4000, seed=a.seed + 1000,
                                   switch_at=p[3], coupon=coupon, **k) for p in set(plans)}

    if engine == "numba":
        res = HF.optimize(horse, M, a.optimize, seed=a.seed, progress=progress, low_memory=a.low_memory,
                          coupon=planned, **kw)
        searched = ("every plan: at30, and coursier / coursier_v2 with every start level and spending cap; "
                    f"coursier_switch with every start level and threshold {H.SWITCH_TS[0]}-{H.SWITCH_TS[-1]}, on a "
                    "grid of spending caps refined around the best; level-30 cleanup computed exactly (fast engine)")
    else:
        res = H.optimize(horse, M, a.optimize, seed=a.seed, progress=progress, coupon=planned, **kw)
        searched = ("a grid of plans (coursier, coursier_v2, coursier_switch, once, hard), then every start level, "
                    "spending cap and threshold around the best ones (plain-Python engine)")
    nw = next(iter(res.values()))["wanted_total"]
    print(head)
    print(f"# level {a.level} -> 30 | tickets {a.tickets} | wanted: {nw} skills | {len(res)} plans in stage 2 | "
          f"{time.time() - t0:.0f}s")
    print(f"# {a.learned_text}")
    n = len(learned)
    print(f"# Searched: {searched}.")
    if planned:
        print("# With a Selection Coupon PLANNED: every chance below includes it, used at the very end on the last")
        print("# missing skill (needs an unwanted skill to change); every Change Coupon, while leveling and at level 30,")
        print("# aims at the SECOND rarest missing skill (the rarest is kept for the Selection Coupon). That targeting is")
        print("# only better if you do use the coupon; as a mere safety net, use --selection-coupon fallback.")
    print("# For each budget: the plans tied with the best (within 1 point for the full set, 0.05 skill for the")
    print("# average), as spans: 'from lvl' = level to start swapping, 'keep' = coupons kept for the level-30 cleanup;")
    print("# coursier_switch: V0 = coursier swaps, V2 = coursier_v2 swaps, learned skills don't count innate ones.")
    print("# The spans cover the tied plans; not every combination inside a span is tied.")
    print("coupons\tfull set: chance\ttied plans\tmost wanted: avg\ttied plans\tat30: chance, avg")
    at30 = res[("at30", 1, 0, 0)]
    best_full = []
    for B in range(a.optimize + 1):
        tf = H.tied_plans(res, B, "full", 0.01)
        tw = H.tied_plans(res, B, "wanted", 0.05)
        best_full.append(res[tf[0]]["full"][B])
        print(f"{B}\t{100 * res[tf[0]]['full'][B]:.1f}%\t{H.describe_plans(tf, B, n, a.level)}\t"
              f"{res[tw[0]]['wanted'][B]:.2f}\t{H.describe_plans(tw, B, n, a.level)}\t"
              f"{100 * at30['full'][B]:.1f}%, {at30['wanted'][B]:.2f}")
    for t in (0.5, 0.8, 0.9, 0.95):
        b = next((B for B, x in enumerate(best_full) if x >= t), None)
        b30 = next((B for B, x in enumerate(at30["full"]) if x >= t), None)
        print(f"# coupons for a {t:.0%} chance of the full set: {b if b is not None else '> max'} with the best plan, "
              f"{b30 if b30 is not None else '> max'} with at30")
    print()
    if a.always_best:
        print("# Suggested plan per budget (full set): the best plan found (--always-best).")
    else:
        print("# Suggested plan per budget (full set): the general rule's plan when it's within 1 point of the best")
        print("# plan found, else the best (--always-best: always the best).")
    print("# V0 = coursier swaps (once per level: Fore Chop, then Hind Kick, if held), V2 = coursier_v2 swaps (once")
    print("# per level: Hind Kick only); learned skills don't count innate ones; keep = coupons kept for level 30.")
    print("# <=1 / <=2 missing: chance of missing at most 1 / 2 wanted skills; worst 5%: wanted skills the worst 5% of")
    print(f"# horses miss ({H.TAILS}+ = {H.TAILS} or more); used: coupons used on average (a horse that doesn't get the")
    print("# full set counts every coupon it used); per full set: used / full set (more failures make it higher).")
    sug = {B: H.suggested_plan(res, B, 0.01, a.level, a.always_best, wanted) for B in range(1, a.optimize + 1)}
    extra_head, extras = "", []
    if a.selection_coupon == "fallback":
        print("# with Selection Coupon: the full-set chance if, at level 30, you decide to use your Selection Coupon")
        print("# at the end (from then on, Change Coupons aim at the second rarest missing skill, the coupon fills")
        print("# the last one). Leveling and the plans above don't change: decide at 30, depending on how it went.")
        extra_head += "\twith Selection Coupon"
        extras.append(evaluate([v[0] for v in sug.values()], coupon="fallback"))
    if a.tickets:
        print(f"# keeping tickets: the full-set chance if you don't use your {a.tickets} Level Down Ticket(s) (the same")
        print("# plan); the other columns use them on every level-up that teaches nothing, from now on.")
        extra_head += "\tkeeping tickets"
        extras.append(evaluate([v[0] for v in sug.values()], coupon=planned, tickets=0))
    print("coupons\tsuggested plan\tfull set\t<=1 missing\t<=2 missing\tworst 5%\tused\tper full set" + extra_head
          + "\tsource")
    for B in range(1, a.optimize + 1):
        plan, src, rc = sug[B]
        best = res[H.tied_plans(res, B, "full", 0)[0]]["full"][B]
        note = (f"rule (best {100 * best:.1f}%)" if src == "rule"
                else f"best (rule: {'not checked' if rc is None else f'{100 * rc:.1f}%'})")
        tl = res[plan]["tails"][B]
        w5 = H.worst5(tl)
        ex = "".join(f"\t{100 * e[plan]['full'][B]:.1f}%" for e in extras)
        u, f = res[plan]["used"][B], res[plan]["full"][B]
        print(f"{B}\t{H.plan_name(plan, B, n, a.level)}\t{100 * f:.1f}%\t{100 * tl[1]:.1f}%\t{100 * tl[2]:.1f}%\t"
              f"{w5 if w5 is not None else f'{H.TAILS}+'}\t{u:.2f}\t{f'{u / f:.2f}' if f else '-'}{ex}\t{note}")
    # average learned skills per level, one column per suggested plan (the budgets it's suggested for)
    groups = {}
    for B in range(1, a.optimize + 1):
        groups.setdefault(sug[B][0], []).append(B)
    span = lambda bs: ",".join(f"{x[0]}" if x[0] == x[-1] else f"{x[0]}-{x[-1]}" for x in _runs(bs))
    if a.coupons_used is not None:
        coupons_used_report(a, horse, M, kw, engine, planned, sug, span, n)
    k = {k2: v for k2, v in kw.items() if k2 != "start_level"}
    if engine == "numba":
        ev = HF.Evaluator(horse, M, max_budget=a.optimize, **kw)
        curves = {p: ev.learned_by_level(p, 4000, a.seed + 1000, planned) for p in groups}
    else:
        curves = {p: H.learned_by_level(horse, M, p, 1000, a.seed + 1000, a.level, coupon=planned, **k) for p in groups}
    cols = []                                     # merge plans whose averages stay within 0.2 skills at every level
    for p, bs in groups.items():
        c = next((c for c in cols if max(abs(curves[p][L] - curves[c[0]][L]) for L in curves[p]) < 0.2), None)
        if c:
            c[1].extend(bs)
        else:
            cols.append([p, list(bs)])
    print()
    print("# Average learned skills (innate ones not counted) when reaching each level, for the suggested plans (the")
    print("# columns: coupon budgets; plans within 0.2 skills of each other share a column). Compare your horse at its")
    print("# level: below average means leveling is going worse than usual."
          + (" Level Down Tickets are used on every level-up that teaches nothing." if a.tickets else ""))
    print("level\t" + "\t".join(f"{span(sorted(bs))} coupons" for _, bs in cols))
    for L in range(a.level, 31):
        print(f"{L}\t" + "\t".join(f"{curves[p][L]:.1f}" for p, _ in cols))
    return 0


def coupons_used_report(a, horse, M, kw, engine, planned, sug, span, n):
    """--coupons-used: for the suggested plans of the chosen budgets, the chance of the full set with at most B
    coupons in total (each plan followed as planned while leveling, then the level-30 cleanup until the full set),
    and the spread of coupons used. Same horses as the suggested-plan table (its full-set column at the plan's own
    budget)."""
    from bdo import horses_fast as HF
    C = max(20, a.optimize + 10)
    groups = {}
    for B in a.used_budgets:
        groups.setdefault(sug[B][0], []).append(B)
    plans = list(groups)
    if engine == "numba":
        ev = HF.Evaluator(horse, M, max_budget=C, low_memory=a.low_memory, **kw)
        r = ev.plans(sorted(set(plans)), 4000, a.seed + 1000, coupon=planned, used=True, at_most=True)
    else:
        r = {p: H.simulate_plan(horse, M, p[0], p[1], p[2], C, runs=4000, seed=a.seed + 1000, switch_at=p[3],
                                coupon=planned, **kw) for p in plans}
    lab = {p: f"{span(bs)} coupon{'s' if bs != [1] else ''}" for p, bs in groups.items()}
    print()
    print("# Coupons used by the suggested plans (--coupons-used): each plan followed as planned while leveling (as for")
    print("# its own budget), then the level-30 cleanup goes on until the full set, up to "
          f"{C} coupons in total. Same horses as above.")
    for p in plans:
        print(f"# plan for {lab[p]}: {H.plan_name(p, None, n, a.level)}")
    print("# at most B coupons: chance of the full set with at most B coupons in total. At a plan's own budget, it's")
    print("# the 'full set' column above; below it, only the horses whose leveling spent fewer coupons can count.")
    print("# Rows stop once every plan is at 99% (see the 99% column below).")
    am = {p: r[p]["at_most"] for p in plans}
    last = next((B for B in range(C + 1) if all(am[p][B] >= 0.99 for p in plans)), C)
    last = min(C, max(last, max(a.used_budgets) + 2))
    print("at most B coupons\t" + "\t".join(f"plan for {lab[p]}" for p in plans))
    for B in range(last + 1):
        print(f"{B}\t" + "\t".join(f"{100 * am[p][B]:.1f}%" for p in plans))
    q = lambda p, x: next((str(B) for B, v in enumerate(am[p]) if v >= x - 1e-9), f">{C}")
    print(f"# average: coupons used on average, with up to {C} (a horse still missing a skill counts every coupon it")
    print(f"# used); median / 90% / 99%: coupons that give the full set to half / 90% / 99% of horses (>{C}: more).")
    print(f"# full set with {C}: chance of the full set with up to {C} coupons in total.")
    print(f"plan\taverage\tmedian\t90%\t99%\tfull set with {C}")
    for p in plans:
        print(f"plan for {lab[p]}\t{r[p]['used'][C]:.2f}\t{q(p, 0.5)}\t{q(p, 0.9)}\t{q(p, 0.99)}\t{100 * am[p][C]:.1f}%")


def _runs(values):
    """[1, 2, 3, 5, 7, 8] -> [[1, 2, 3], [5], [7, 8]]"""
    out = []
    for v in values:
        if out and v == out[-1][-1] + 1:
            out[-1].append(v)
        else:
            out.append([v])
    return out

if __name__ == "__main__":
    sys.exit(main())
