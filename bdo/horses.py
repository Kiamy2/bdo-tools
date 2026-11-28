"""Horse skill learning: the in-game odds formula and a leveling simulator.

Model (fitted to the in-game "Growth simulator" on 2026-11-17, see docs/horse-skills-report.md):

    chance of skill i on a level-up = M * w_i / (sum of w over skills not yet learned + W)
    chance of no skill              = 1 - sum of the above
    if the skill chances would add up to more than 100%, they are rescaled to exactly 100%.

- w_i: the skill's weight (the "learn chance" databases list, e.g. bdolytics), W: the horse's no-skill weight.
- M = 1 + Training bonus + 0.10 (Pearl horse gear, 4 pieces) + 0.10 (Mount Brand Spell Stone), same for every tier.
- W is per horse: 100 - sum of all weights for the Mythical Diné and the Doom checked, but not for the T8 checked.
- One outcome per level-up. The horse's level doesn't change the odds.
- Mount Skill Change Coupon: draws among unlearned skills (minus the one removed) with the same weights;
  the desired skill's weight is multiplied by (1 + point_bonus * Skill Change Points). Each coupon adds 1 point,
  except one that gives the desired skill: the points go back to 0 (seen in-game, 2026-11-19).
"""
import bisect
import json
import math
import os
import random

from .items import compact

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "horse_skills.json")

# Training level -> skill learn bonus (%). Community sheet (docs/horse-skills-report.md);
# Professional 10 and Artisan 7 were checked in-game.
_TIERS = {
    "Beginner": [0, 1, 1.3, 1.6, 1.9, 2.2, 2.5, 2.8, 3.1, 3.4],
    "Apprentice": [3.7, 4.1, 4.4, 4.7, 5, 5.4, 5.7, 6, 6.4, 6.7],
    "Skilled": [7.1, 7.4, 7.8, 8.1, 8.5, 8.9, 9.2, 9.6, 9.9, 10.3],
    "Professional": [10.9, 11.6, 12.3, 12.9, 13.6, 14.2, 14.8, 15.5, 16.1, 16.8],
    "Artisan": [17.5, 18.2, 18.9, 19.6, 20.3, 21, 21.7, 22.4, 23.1, 23.8],
    "Master": [24.6, 25.3, 26.1, 26.8, 27.6, 28.3, 29.1, 29.8, 30.6, 31.4, 32.6, 33.9, 35.1, 36.4, 37.7, 39,
               40.3, 41.5, 42.8, 44.1, 45.5, 46.8, 48.2, 49.5, 50.9, 52.3, 53.6, 55, 56.3, 57.7],
    "Guru": [59.1, 60.6, 62, 63.5, 64, 66.3, 67.8, 69.2, 70.7, 72.1, 73.9, 75.7, 77.5, 79.3, 81.1, 82.9, 84.7,
             86.5, 88.3] + [100] * 31,
}
_TIER_FR = {"debutant": "Beginner", "apprenti": "Apprentice", "qualifie": "Skilled", "professionnel": "Professional",
            "artisan": "Artisan", "maitre": "Master", "gourou": "Guru"}
GEAR = BRAND = 0.10
# Learn-chance boosts: the Pearl horse gear set and the Mount Brand Spell Stone (+10% each).
BOOSTS = {"none": (0, 0), "gear": (1, 0), "brand": (0, 1), "both": (1, 1)}
BOXES = BOOSTS  # older name

# Default wanted list: skills for travel. Skills a horse can't learn are ignored.
TRAVEL_SET = ["Sprint", "Instant Accel", "S: Instant Accel", "Drift", "High Jump", "Streak Leap", "Start Accel",
              "Quick Ride", "Charge", "Sideways", "S: Sideways", "Quick Back", "Quick Stop",
              # Dream / Mythical / Voltarion skills that can be learned (not innate)
              "Wings of Freedom", "Earth of Protection", "Dark Sprint", "Lightning Charge",
              "Instant Accel: Flash", "Drift: Flash", "Thunderfall"]
# Courser set: what a T8 needs (with level 30) to become a Dream Horse (T9) through courser training.
COURSER_SET = ["Charge", "Drift", "Sprint", "Instant Accel", "Sideways", "S: Instant Accel", "S: Sideways"]
WANTED_SETS = {"travel": TRAVEL_SET, "courser": COURSER_SET}


def default_wanted_set(horse):
    """The horse_skills tool's default target set: 'courser' for a T8 (Dream Horse goal), else 'travel'. (Library
    functions keep TRAVEL_SET as their default.)"""
    return "courser" if horse.tier == 8 else "travel"


CLASSIC_FODDER = ["Fore Chop", "Hind Kick"]       # in the order S1 swaps them (C42: Fore Chop first is a bit better)
STRATEGIES = ["natural", "at30", "coursier", "coursier_v2", "coursier_switch", "once", "hard", "ideal"]
SWITCH_TS = list(range(9, 17))
TAILS = 5                                       # bad-outcome chances: missing at most 0..4 wanted skills                  # thresholds the optimizer tries for coursier_switch
DEFAULT_SWITCH_AT = 12
STRATEGY_HELP = {
    "natural": "no coupons used",
    "at30": "level naturally, spend all coupons at level 30 on unwanted skills",
    "coursier": "S1: once per level: swap Fore Chop, then Hind Kick, if held (keeping a reserve), rest at 30",
    "coursier_v2": "S2: swap only Hind Kick (the heavier of the two) each time it's learned and keep Fore Chop: no "
                   "Hind Kick <-> Fore Chop loop (keeping a reserve), rest at 30. Best with few coupons",
    "coursier_switch": "S1-S2: coursier until the horse has --switch-at learned skills (default 12; innate skills don't "
                       "count), then coursier_v2 (keeping a reserve), rest at 30. Best with many coupons",
    "once": "swap every unwanted skill once when it's learned (keeping a reserve), rest at 30",
    "hard": "swap every unwanted skill until a wanted one comes (keeping a reserve), rest at 30",
    "ideal": "unlimited coupons: always hold the rarest skills, for the most skills at 30",
}


class DataError(ValueError):
    pass


def training_bonus(text):
    """'Artisan 7', 'artisan7', 'Maître 20', '21.7' or '21.7%' -> bonus in % (float)."""
    t = compact(text)
    try:
        return float(t.rstrip("%"))
    except ValueError:
        pass
    for key in list(_TIERS) + list(_TIER_FR):
        k = compact(key)
        if t.startswith(k) and t[len(k):].isdigit():
            tier = _TIER_FR.get(k, key) if k in _TIER_FR else key
            levels = _TIERS[tier]
            n = int(t[len(k):])
            if tier == "Guru" and n >= 20:
                return 100.0                         # the sheet stops at Guru 50; the game goes higher (Guru 57 seen)
            if 1 <= n <= len(levels):
                return levels[n - 1]
    raise DataError(f"unknown Training level {text!r} (e.g. 'Artisan 7', 'Master 20', or a bonus like 21.7)")


class Horse:
    def __init__(self, name, weights, no_skill_weight, born_with=(), tier=None, source="", date="", notes=""):
        self.name, self.tier, self.source, self.date, self.notes = name, tier, source, date, notes
        self.weights = dict(weights)                 # learnable skills -> weight (%)
        self.born_with = list(born_with)             # innate skills (shown as 100% by databases)
        self.W = float(no_skill_weight)
        if self.W < 0:
            raise DataError(f"{name}: negative no-skill weight")

    def with_innate(self, skills):
        """The same horse with these learnable skills innate instead (out of the draw, held from the start); the
        'no skill' weight is kept (true for the special T8s read so far but one: check with a simulator reading)."""
        bad = [s for s in skills if s not in self.weights and s not in self.born_with]
        if bad:
            raise DataError(f"{self.name}: can't learn {', '.join(bad)}")
        extra = [s for s in dict.fromkeys(skills) if s in self.weights]
        return Horse(f"{self.name} + innate {', '.join(extra)}" if extra else self.name,
                     {s: w for s, w in self.weights.items() if s not in extra}, self.W, self.born_with + extra,
                     self.tier, self.source, self.date, self.notes)

    def M(self, bonus, gear=False, brand=False):
        return 1 + bonus / 100 + GEAR * gear + BRAND * brand

    def odds(self, M, learned=()):
        """Chance of each unlearned skill on the next level-up, and of no skill (fractions)."""
        un = [s for s in self.weights if s not in learned]
        su = sum(self.weights[s] for s in un)
        k = M / (su + self.W)
        if k * su > 1:
            k = 1 / su                               # cap: rescaled to 100%
        p = {s: k * self.weights[s] for s in un}
        return p, 1 - sum(p.values())


def load_data(path=DATA_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def horse_names(data):
    return list(data["horses"])


def get_horse(data, name):
    want = compact(name)
    for key, h in data["horses"].items():
        if want in [compact(x) for x in [key] + h.get("aliases", [])]:
            return Horse(key, h["weights"], h["no_skill_weight"], h["born_with"], h.get("tier"), h.get("source", ""),
                         h.get("date", ""), h.get("no_skill_weight_note", ""))
    raise DataError(f"unknown horse {name!r}; known: {', '.join(data['horses'])}")


def typed_name(data, name):
    """The data's spelling of the name or alias the user typed (e.g. 'T8 Type 6', an alias of 'T8 Type 4')."""
    want = compact(name)
    for key, h in data["horses"].items():
        for x in [key] + h.get("aliases", []):
            if compact(x) == want:
                return x
    return name


def sure_hits(horse, learned, wanted):
    """The skills left to learn when every one of them is wanted (any swap then gives a wanted skill), else []."""
    left = [s for s in horse.weights if s not in set(learned)]
    return left if left and set(left) <= set(wanted) else []


def skill_resolver(data):
    """Returns f(name) -> English skill name, accepting English or French, accents/spaces optional."""
    idx = {}
    for en, fr in data["skills_fr"].items():
        idx[compact(en)] = en
        if fr:
            idx[compact(fr)] = en
    def resolve(name):
        en = idx.get(compact(name))
        if not en:
            raise DataError(f"unknown skill {name!r}")
        return en
    return resolve


def horse_from_sim_file(path, resolve):
    """A horse from an in-game simulator reading (CSV 'skill,percent' rows plus '# key: value' headers).

    Headers: name, tier (e.g. 8; sets the default target set), type (the in-game type, shown), training (e.g.
    Artisan 7), boosts (none/gear/brand/both; 'boxes' also accepted), innate (the 'base skill' ones), learned (skills
    marked learned or 'base skill' at the reading; both headers take them out of the draw), comma-separated. Needs a
    'none' row (Compétence non apprise) above 0%.
    """
    meta, rows = {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                k, _, v = line[1:].partition(":")
                meta[k.strip().lower()] = v.strip()
                continue
            name, _, val = line.rpartition(",")
            rows[name.strip()] = float(val.strip().rstrip("%"))
    none = next((v for k, v in rows.items() if compact(k) in (compact("none"), compact("Compétence non apprise"))), None)
    if none is None or none <= 0:
        raise DataError("the reading needs a 'none' row above 0% (take it at a lower Training level, without boosts)")
    boosts = meta.get("boosts", meta.get("boxes", "none")).lower()
    if boosts not in BOOSTS:
        raise DataError(f"boosts must be one of {', '.join(BOOSTS)}, not {boosts!r}")
    gear, brand = BOOSTS[boosts]
    M = 1 + training_bonus(meta.get("training", "")) / 100 + GEAR * gear + BRAND * brand
    learned = [resolve(s) for s in (meta.get("innate", "") + "," + meta.get("learned", "")).split(",") if s.strip()]
    w = {resolve(k): v / M for k, v in rows.items() if compact(k) not in (compact("none"), compact("Compétence non apprise"))}
    # normalise so that (sum of unlearned weights + W) = 100 at the reading
    W = 100 - sum(w.values())
    tier = meta.get("tier", "").upper().lstrip("T")
    if tier and not tier.isdigit():
        raise DataError(f"tier must be a number like 8 or T8, not {meta['tier']!r}")
    name = meta.get("name", os.path.basename(path)) + (f" (in-game type {meta['type']})" if meta.get("type") else "")
    return Horse(name, w, W, list(dict.fromkeys(learned)), int(tier) if tier else None,
                 source=f"simulator reading ({path})", date=meta.get("date", ""))


# --- simulation ----------------------------------------------------------------------------------------------

WHEN_STUCK = """A horse is stuck when it reaches level 30 with fewer learned skills than wanted ones: no Change Coupon can
then complete the set (a coupon never changes the skill count; a Selection Coupon needs an unwanted skill to change).
when_stuck='stop' (default): every plan stops spending as soon as the horse is certainly stuck: while leveling, once
its learned skills plus the level-ups left are fewer than the wanted skills (a level-up teaches at most one skill,
a Level Down Ticket only redoes an empty one); at level 30, a stuck horse doesn't start the cleanup. Every number
then describes that way of playing. 'continue': as before 2026-11-23: the plan's swaps go on, and the level-30
cleanup swaps unwanted skills until none is left or the coupons run out (for a player who'd still improve a stuck
horse: more wanted skills, never the full set)."""


def _halt(when_stuck):
    if when_stuck not in ("stop", "continue"):
        raise DataError(f"when_stuck must be 'stop' or 'continue', not {when_stuck!r}")
    return when_stuck == "stop"


def _cycle_skill(fodder, wt):
    """S2 cycles exactly one fodder skill, the heaviest, and keeps the others: a swap of it can then never draw
    another fodder skill back, so coupons don't churn between them. On ties: Hind Kick if it's one of them, else the
    first in the list (the T8 weighs both the same)."""
    return max(fodder, key=lambda s: (wt[s], s == "Hind Kick")) if fodder else None


def _rarest_unwanted(have, wanted, rank):
    """Level-30 cleanup rule: swap the rarest unwanted skill held. A swapped-away skill goes back into the coupon
    draw, so the common ones (Hind Kick...) stay held until last. Checked against the best possible cleanup
    (any skill to swap, any desired skill): no measurable difference for the full set."""
    junk = [s for s in have if s not in wanted]
    return min(junk, key=lambda s: rank[s]) if junk else None


def _draw(rng, items, weights):
    x = rng.random() * sum(weights)
    for s, w in zip(items, weights):
        x -= w
        if x < 0:
            return s
    return items[-1] if items else None


def simulate(horse, M, strategy, coupons=30, tickets=0, start_level=1, learned=(), wanted=None, fodder=None,
             point_bonus=0.25, points=0, runs=5000, seed=1, max_level=30, reserve=0, swap_from=1,
             switch_at=DEFAULT_SWITCH_AT, when_stuck="stop"):
    """Monte Carlo of leveling start_level -> max_level. Returns averages over runs.
    when_stuck: see WHEN_STUCK.

    reserve: coupons the coursier/once/hard strategies keep for the level-30 cleanup (no swaps while leveling below it).
    swap_from: horse level from which coursier/once/hard start swapping while leveling (before it, they wait).
    switch_at: coursier_switch swaps like coursier until the horse holds this many learned skills (checked from
    swap_from on), then like coursier_v2 for good.
    """
    rng = random.Random(seed)
    pool = list(horse.weights)
    wt = horse.weights
    wanted = set(TRAVEL_SET if wanted is None else wanted) & set(pool)
    halt = _halt(when_stuck)
    fodder = [s for s in (CLASSIC_FODDER if fodder is None else fodder) if s in wt and s not in wanted]
    rare = sorted(pool, key=lambda s: wt[s])
    rank = {s: (wt[s], i) for i, s in enumerate(pool)}
    cyc = _cycle_skill(fodder, wt)
    tot_sum = wanted_sum = all_count = used_sum = 0
    misses = []
    for _ in range(runs):
        have = set(s for s in learned if s in wt)
        c = 0 if strategy == "natural" else coupons
        t, pts = tickets, points
        latched = False                              # coursier_switch: switched to the S2 swaps

        def swap(out):
            nonlocal c, pts
            cands = [s for s in pool if s not in have and s != out]
            if not cands or c <= 0:
                return None
            target = min((s for s in wanted if s in cands), key=lambda s: wt[s], default=None)
            ws = [wt[s] * (1 + point_bonus * pts) if s == target else wt[s] for s in cands]
            new = _draw(rng, cands, ws)
            have.discard(out)
            have.add(new)
            c -= 1
            pts = 0 if new == target else pts + 1
            return new

        for _lvl in range(start_level, max_level):
            while True:
                un = [s for s in pool if s not in have]
                su = sum(wt[s] for s in un)
                k = min(M / (su + horse.W), 1 / su) if su else 0
                x, got = rng.random(), None
                for s in un:
                    x -= k * wt[s]
                    if x < 0:
                        got = s
                        break
                if got or t == 0:
                    break
                t -= 1                               # Mount Level Down Ticket: redo this level
            if got:
                have.add(got)
            if strategy == "coursier_switch" and _lvl + 1 >= swap_from and len(have) >= switch_at:
                latched = True                       # from now on, S2 swaps only
            if strategy == "ideal":
                have = set(rare[:len(have)])
            elif _lvl + 1 < swap_from:                 # level just reached is below swap_from: no swaps yet
                pass
            elif halt and len(have) + max_level - (_lvl + 1) < len(wanted):
                pass                                 # certainly stuck: no swap can help any more
            elif strategy == "coursier" or (strategy == "coursier_switch" and not latched):
                for s in fodder:
                    if s in have and c > reserve:
                        swap(s)
            elif strategy in ("coursier_v2", "coursier_switch"):
                if cyc in have and c > reserve:
                    swap(cyc)
            elif strategy == "once":
                # swap each unwanted skill once when it's learned; at swap_from, also those learned while waiting
                todo = sorted(have - wanted, key=lambda s: wt[s]) if _lvl + 1 == swap_from > 1 else [got]
                for s in todo:
                    if s and s not in wanted and s in have and c > reserve:
                        swap(s)
            elif strategy == "hard":
                for s in sorted(have - wanted, key=lambda s: wt[s]):
                    if s in have and c > reserve:
                        slot = s
                        while slot not in wanted and c > reserve:
                            slot = swap(slot)
                            if slot is None:
                                break
        if (strategy in ("at30", "coursier", "coursier_v2", "coursier_switch", "once", "hard")
                and not (halt and len(have) < len(wanted))):     # a stuck horse stops (when_stuck = stop)
            while c > 0 and not wanted <= have:      # level-30 cleanup (see _rarest_unwanted)
                out = _rarest_unwanted(have, wanted, rank)
                if out is None or swap(out) is None:
                    break
        n = len(have)
        nw = min(n, len(wanted)) if strategy == "ideal" else len(have & wanted)
        tot_sum += n
        wanted_sum += nw
        all_count += nw == len(wanted)
        misses.append(len(wanted) - nw)
        used_sum += 0 if strategy in ("natural", "ideal") else coupons - c
    misses.sort()
    return {"skills": tot_sum / runs, "wanted": wanted_sum / runs, "all_wanted": all_count / runs,
            "missing_le1": sum(m <= 1 for m in misses) / runs, "worst5_missing": percentile(misses, 0.95),
            "coupons_used": used_sum / runs, "wanted_total": len(wanted), "pool_total": len(pool)}


def coupons_needed(horse, M, strategy, target, max_coupons=150, cache=None, **kw):
    """Smallest coupon budget whose chance of ending with every wanted skill is at least target (0-1).

    Bisection over the budget; returns None if max_coupons isn't enough. kw goes to simulate(). Pass the same
    cache dict for several targets to reuse simulations. Assumes the chance grows with the budget, which holds
    up to simulation noise (so the answer is good to about +/-1 coupon).
    """
    cache = {} if cache is None else cache

    def chance(n):
        if n not in cache:
            cache[n] = simulate(horse, M, strategy, n, **kw)["all_wanted"]
        return cache[n]

    if chance(max_coupons) < target:
        return None
    lo, hi = -1, max_coupons                      # chance(lo) < target <= chance(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if mid >= 0 and chance(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


# --- plans and optimizer ---------------------------------------------------------------------------------------
# A plan = (strategy, swap_from, spend_cap, switch_at): swap while leveling from level swap_from on, spending at most
# spend_cap coupons, then do the level-30 cleanup with whatever is left. switch_at is coursier_switch's threshold
# (learned skills); 0 for the other strategies. For a budget B >= spend_cap this is the same as
# "keep B - spend_cap coupons for level 30". One simulation of a plan gives its result for every budget at once:
# the cleanup is run with as many coupons as it takes, and a budget B simply stops it after B coupons in total.

def simulate_plan(horse, M, strategy, swap_from=1, spend_cap=0, max_budget=60, tickets=0, start_level=1, learned=(),
                  wanted=None, fodder=None, point_bonus=0.25, points=0, runs=4000, seed=1, max_level=30,
                  switch_at=DEFAULT_SWITCH_AT, coupon=None, when_stuck="stop", end_level=None, ticket_from=0,
                  ticket_curve=None):
    """Monte Carlo of one plan for every budget 0..max_budget. switch_at: see simulate(). when_stuck: see
    WHEN_STUCK (end_level: the level the 'certainly stuck' test counts level-ups to; default max_level).
    Level Down Tickets: on a level-up that teaches nothing, from level ticket_from on, and (with ticket_curve, indexed
    by level) only while the horse has fewer learned skills than ticket_curve[level reached] (see
    horses_fast.Evaluator.ticket_curve). The result has tickets_used (average).
    coupon: a Mount Skill Selection Coupon used at the very end on the last missing skill, if the horse holds an
    unwanted skill to change (at least as many learned skills as wanted ones). 'planned': every Change Coupon keeps
    the rarest missing skill for it (desired skill = the second rarest missing); 'fallback': only the level-30
    cleanup does (a choice made at level 30); None: no Selection Coupon. 'natural' uses no coupon of any kind.

    Returns a dict: full[B] (chance of every wanted skill with B coupons), wanted[B] (average wanted skills),
    used[B] (average Change Coupons used: while leveling, then the cleanup until done or stuck),
    tails[B] (chances of missing at most 0..TAILS - 1 wanted skills), for B >= spend_cap (None below); skills (average skills at 30, budget-independent); needed (sorted coupons
    needed per run for the full set, inf when the horse has too few skills); at_most[B] for every B (the chance of
    the full set with at most B coupons in total, the plan followed as planned: see horses_fast.Evaluator.plans);
    stuck (share of runs ending with fewer learned skills than wanted ones), used_ok[B] (average coupons used by
    the other runs); skill_counts (sorted, per run).
    """
    rng = random.Random(seed)
    pool = list(horse.weights)
    wt = horse.weights
    wanted = set(TRAVEL_SET if wanted is None else wanted) & set(pool)
    halt = _halt(when_stuck)
    end = max_level if end_level is None else end_level
    fodder = [s for s in (CLASSIC_FODDER if fodder is None else fodder) if s in wt and s not in wanted]
    rank = {s: (wt[s], i) for i, s in enumerate(pool)}
    cyc = _cycle_skill(fodder, wt)
    if strategy == "at30":
        spend_cap = 0
    nb = max_budget + 1
    full_n, wanted_sum, used_sum, used_ok, n_ok, tickets_used = [0] * nb, [0] * nb, [0] * nb, [0] * nb, 0, 0
    used_sq = [0] * nb
    tail_n = [[0] * TAILS for _ in range(nb)]
    needed, counts = [], []
    for _ in range(runs):
        have = set(s for s in learned if s in wt)
        spent, t, pts = 0, tickets, points
        latched = False

        def swap(out, keep=False):
            nonlocal spent, pts
            cands = [s for s in pool if s not in have and s != out]
            if not cands:
                return None
            missing = sorted((s for s in wanted if s in cands), key=lambda s: rank[s])
            target = (missing[1] if keep and len(missing) >= 2 else missing[0]) if missing else None
            ws = [wt[s] * (1 + point_bonus * pts) if s == target else wt[s] for s in cands]
            new = _draw(rng, cands, ws)
            have.discard(out)
            have.add(new)
            spent += 1
            pts = 0 if new == target else pts + 1
            return new

        for _lvl in range(start_level, max_level):
            while True:
                un = [s for s in pool if s not in have]
                su = sum(wt[s] for s in un)
                k = min(M / (su + horse.W), 1 / su) if su else 0
                x, got = rng.random(), None
                for s in un:
                    x -= k * wt[s]
                    if x < 0:
                        got = s
                        break
                if got or t == 0 or _lvl + 1 < ticket_from or (
                        ticket_curve is not None and len(have) >= ticket_curve[_lvl + 1]):
                    break                                # (ticket policy: from ticket_from, while behind the curve)
                t -= 1
            if got:
                have.add(got)
            if _lvl + 1 < swap_from or spent >= spend_cap:
                continue
            if halt and len(have) + end - (_lvl + 1) < len(wanted):
                continue                             # certainly stuck: no swap can help any more
            if strategy == "coursier_switch" and len(have) >= switch_at:
                latched = True                       # from now on, S2 swaps only
            kp = coupon == "planned"
            if strategy == "coursier" or (strategy == "coursier_switch" and not latched):
                for s in fodder:
                    if s in have and spent < spend_cap:
                        swap(s, kp)
            elif strategy in ("coursier_v2", "coursier_switch"):
                if cyc in have and spent < spend_cap:
                    swap(cyc, kp)
            elif strategy == "once":
                todo = sorted(have - wanted, key=lambda s: wt[s]) if _lvl + 1 == swap_from > 1 else [got]
                for s in todo:
                    if s and s not in wanted and s in have and spent < spend_cap:
                        swap(s, kp)
            elif strategy == "hard":
                for s in sorted(have - wanted, key=lambda s: wt[s]):
                    slot = s
                    while slot is not None and slot not in wanted and slot in have and spent < spend_cap:
                        slot = swap(slot, kp)
        counts.append(len(have))
        tickets_used += tickets - t
        ok = len(have) >= len(wanted)                # not stuck: enough skills for the full set
        n_ok += ok
        base = spent
        sel = coupon is not None and strategy != "natural"
        spare = sel and len(have) >= len(wanted)     # an unwanted skill for the Selection Coupon to change
        stop = 1 if sel else 0                       # with it, the cleanup stops at one missing skill
        traj = [len(have & wanted)]                  # wanted skills after 0, 1, 2... cleanup coupons
        if strategy != "natural" and not (halt and not ok):              # a stuck horse stops (when_stuck = stop)
            while len(wanted - have) > stop and len(traj) < 100000:      # level-30 cleanup (see _rarest_unwanted)
                out = _rarest_unwanted(have, wanted, rank)
                if out is None or swap(out, sel) is None:
                    break
                traj.append(len(have & wanted))
        if spare:                                    # the Selection Coupon fills the last missing skill
            traj = [min(len(wanted), x + 1) for x in traj]
        need = base + len(traj) - 1 if traj[-1] == len(wanted) else float("inf")
        needed.append(need)
        last = len(traj) - 1
        for B in range(spend_cap, nb):
            j = B - base
            if strategy == "natural":
                j = 0
            wanted_sum[B] += traj[min(j, last)]
            used_sum[B] += base + min(j, last)
            used_sq[B] += (base + min(j, last)) ** 2
            if ok:
                used_ok[B] += base + min(j, last)
            full_n[B] += traj[min(j, last)] == len(wanted)
            miss = len(wanted) - traj[min(j, last)]
            for t in range(miss, TAILS):
                tail_n[B][t] += 1
    needed.sort()
    counts.sort()
    return {"full": [full_n[B] / runs if B >= spend_cap else None for B in range(nb)],
            "wanted": [wanted_sum[B] / runs if B >= spend_cap else None for B in range(nb)],
            "tails": [[x / runs for x in tail_n[B]] if B >= spend_cap else None for B in range(nb)],
            "used": [used_sum[B] / runs if B >= spend_cap else None for B in range(nb)],
            "used_se": [_se_mean(used_sum[B], used_sq[B], runs) if B >= spend_cap else None for B in range(nb)],
            "at_most": [bisect.bisect_right(needed, B) / runs for B in range(nb)],
            "stuck": 1 - n_ok / runs,
            "tickets_used": tickets_used / runs,
            "used_ok": [used_ok[B] / n_ok if B >= spend_cap and n_ok else None for B in range(nb)],
            "skills": sum(counts) / runs, "needed": needed, "skill_counts": counts, "wanted_total": len(wanted)}


def _se_mean(total, total_sq, n):
    """Standard error of a mean from the sum and the sum of squares of n values."""
    if n < 2:
        return 0.0
    var = max(0.0, (total_sq - total * total / n) / (n - 1))
    return (var / n) ** 0.5


def worst5(tails):
    """Wanted skills missed by the worst 5% of horses, from tails = [P(missing <= t) for t = 0, 1...]: the smallest
    t with P(missing <= t) >= 95%, or None if it's beyond the tails given."""
    return next((t for t, x in enumerate(tails) if x >= 0.95 - 1e-9), None)


def learned_by_level(horse, M, plan, runs=1000, seed=1, start_level=1, max_level=30, **kw):
    """Average learned skills (innate ones not counted) when reaching each level from start_level to max_level, for
    one plan (strategy, swap_from, spend_cap, switch_at): {level: average}. kw: as simulate_plan."""
    st, lv, cap, T = plan
    return {L: simulate_plan(horse, M, st, lv, cap, 0, runs=runs, seed=seed, start_level=start_level, max_level=L,
                             switch_at=T, end_level=max_level, **kw)["skills"] for L in range(start_level, max_level + 1)}


def percentile(sorted_values, p):
    """Value below which a share p (0-1) of the sorted values falls (nearest rank)."""
    if not sorted_values:
        return None
    i = min(len(sorted_values) - 1, max(0, int(round(p * len(sorted_values) + 0.5)) - 1))
    return sorted_values[i]


PLAN_LEVELS = [1, 4, 7, 10, 13, 16, 18, 20, 22, 24, 26, 28]
PLAN_CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30]


# The general rules (C43, with the points reset; research for the report): one compact plan per budget, by target
# set. Checked with fresh horses over 148 courser situations (the default T8 types x 6 Training levels x 3 boosts,
# and horses partway through leveling) and 60 travel situations (Mythical Diné, Doom and Arduanatt): worst loss
# against each situation's best plan 1.8-3.5 points at 2-8 coupons and at most 1.7 above for the courser set; 1.9-3.9
# at 2-7 and at most 2.5 above for the travel set. Fitted up to 40 coupons; larger budgets use the last band.
def rule_target(wanted=None):
    """'courser' when the wanted skills are the courser set, else 'travel' (the rule's small-budget starts differ)."""
    return "courser" if wanted is not None and set(wanted) == set(COURSER_SET) else "travel"


def rule_plan(budget, start_level=1, wanted=None):
    """The general rule's plan for a coupon budget (N), for the target set of `wanted` (see rule_target):
    N = 1: no swaps while leveling, the coupon at level 30;
    N = 2-24: S2 until level 30, keep 1 coupon, from level max(10, 31 - 1.75 x N) rounded (halves up); for the
              courser set with 2-6 coupons, from level 30 - 2 x N instead (26, 24, 22, 20, 18);
    N >= 25: from level 10, S1 until 12 learned skills, then S2 until level 30, spending at most 24 while leveling.
    A horse already past the start level starts at its next level."""
    if budget <= 1:
        return ("at30", 1, 0, 0)
    if budget <= 24:
        lv = 30 - 2 * budget if rule_target(wanted) == "courser" and budget <= 6 else \
            min(29, max(10, math.floor(31 - 1.75 * budget + 0.5)))
        st, cap, T = "coursier_v2", budget - 1, 0
    else:
        st, lv, cap, T = "coursier_switch", 10, 24, 12
    return (st, max(lv, start_level + 1), cap, T)


def effective_plan(plan, learned_count=0, start_level=0):
    """The plan as it plays out for a horse at start_level that already has learned_count learned skills (innate
    ones not counted): coursier_switch with a threshold the horse has reached is plain coursier_v2, and a start
    level already passed is the next level. A plan whose swaps would start after level 30 (e.g. any plan for a
    level-30 horse) is at30."""
    st, lv, cap, T = plan
    if st in ("natural", "at30"):
        return plan
    if max(lv, start_level + 1) > 30:
        return ("at30", 1, 0, 0)
    if st == "coursier_switch" and learned_count >= T:
        st, T = "coursier_v2", 0
    return (st, max(lv, start_level + 1), cap, T)


# The swapping strategies' names in plan texts: S1 = coursier (once per level: Fore Chop, then Hind Kick, if held),
# S2 = coursier_v2 (once per level: Hind Kick if held, never Fore Chop). Called S1 / S2 before 2026-11-23.
PLAN_LABEL = {"coursier": "S1", "coursier_v2": "S2", "coursier_switch": "S1-S2", "at30": "at30"}
PLAN_CODE = {"s1": "coursier", "s2": "coursier_v2", "s1-s2": "coursier_switch", "at30": "at30"}


def plan_code(plan):
    """A plan in the compact syntax of parse_plan: 's2:L20:C2', 's1-s2:L10:C24:T12', 'at30'."""
    st, lv, cap, T = plan
    if st == "at30":
        return "at30"
    code = {v: k for k, v in PLAN_CODE.items()}.get(st, st)
    return f"{code}:L{lv}:C{cap}" + (f":T{T}" if st == "coursier_switch" else "")


def parse_plan(text):
    """A plan from the compact syntax: strategy (s1, s2, s1-s2 or at30), then the start level L, the spending cap C
    (coupons spent at most while leveling) and for s1-s2 the threshold T (learned skills at which S1 switches to S2),
    separated by ':' in any order: 's2:L20:C2', 's1-s2:L10:C24:T12', 'at30'. Returns (strategy, L, C, T)."""
    parts = [x.strip().lower() for x in text.split(":") if x.strip()]
    st = PLAN_CODE.get(parts[0]) if parts else None
    if st is None:
        raise DataError(f"plan {text!r}: start with s1, s2, s1-s2 or at30 (e.g. s2:L20:C2)")
    if st == "at30":
        if len(parts) > 1:
            raise DataError(f"plan {text!r}: at30 takes nothing else")
        return ("at30", 1, 0, 0)
    f = {}
    for x in parts[1:]:
        if len(x) < 2 or x[0] not in "lct" or not x[1:].isdigit() or x[0] in f:
            raise DataError(f"plan {text!r}: {x!r} isn't L<level>, C<coupons> or T<skills> (e.g. s2:L20:C2)")
        f[x[0]] = int(x[1:])
    need = "lct" if st == "coursier_switch" else "lc"
    name = {"l": "L (start level)", "c": "C (coupons spent at most while leveling)", "t": "T (learned skills to switch at)"}
    if set(f) - set(need):
        raise DataError(f"plan {text!r}: {parts[0]} takes no {', '.join(name[k] for k in set(f) - set(need))}")
    if set(need) - set(f):
        raise DataError(f"plan {text!r}: {parts[0]} also needs " + ", ".join(name[k] for k in need if k not in f))
    if not 1 <= f["l"] <= 30 or f["c"] < 1:
        raise DataError(f"plan {text!r}: L must be 1-30 and C at least 1")
    return (st, f["l"], f["c"], f.get("t", 0))


def plan_name(plan, budget=None, learned_count=0, start_level=0):
    """A plan in words: 'from lvl 10, S1 until 11 learned skills, then S2, keep 5' (S1 = coursier swaps, S2 =
    coursier_v2 swaps: see PLAN_LABEL; keep = coupons kept for the level-30 cleanup, shown when the budget is
    given). In its effective form for a horse at start_level with learned_count learned skills (effective_plan)."""
    st, lv, cap, T = effective_plan(plan, learned_count, start_level)
    if st == "natural":
        return "no coupons"
    if st == "at30":
        return "no swaps while leveling, every coupon at level 30"
    keep = f", keep {budget - cap}" if budget is not None else f", spend <= {cap} while leveling"
    how = {"coursier": "S1 until lvl 30", "coursier_v2": "S2 until lvl 30",
           "coursier_switch": f"S1 until {T} learned skills, then S2"}.get(st, f"{st} until lvl 30")
    return f"from lvl {lv}, {how}{keep}"


def _neighbors(value, grid, lo, hi):
    """Every integer strictly between value's neighbors on the grid (value included), within lo..hi."""
    below = max([g for g in grid if g < value], default=lo - 1)
    above = min([g for g in grid if g > value], default=hi + 1)
    return range(max(lo, below + 1), min(hi, above - 1) + 1)


def optimize(horse, M, max_budget=50, strategies=("coursier", "coursier_v2", "coursier_switch", "once", "hard"),
             levels=None, caps=None, switch_ts=None, runs=(1000, 4000), top=6, max_close=15, refine=True, seed=1,
             progress=None, stage1=None, **kw):
    """Search plans for every budget 0..max_budget, for two goals: 'full' (chance of every wanted skill) and
    'wanted' (average wanted skills). stage1: a dict to fill with the results of every plan tried before stage 2.
    Stage 1: every plan of the grid with runs[0] (coursier_switch: thresholds switch_ts, default every other value of
    SWITCH_TS).
    Refine: around the best and close plans of stage 1, every start level and spending cap between their grid
    neighbors (step 1), and for coursier_switch the thresholds next to theirs (within SWITCH_TS), also with runs[0].
    Stage 2: for each budget and goal, the top plans so far and every plan close to the best (up to max_close),
    again with runs[1] and a fresh seed (to avoid picking a lucky winner, and to know which plans are tied).
    Stage 2 also includes the general rule's plan for every budget (rule_plan), for suggested_plan().
    Returns {plan: simulate_plan result} for the stage-2 plans; plan = (strategy, swap_from, spend_cap, switch_at)."""
    levels = PLAN_LEVELS if levels is None else levels
    caps = PLAN_CAPS if caps is None else caps
    switch_ts = SWITCH_TS[::2] if switch_ts is None else switch_ts
    max_level = kw.get("max_level", 30)
    found = {}

    def run_all(plans, label):
        todo = [p for p in plans if p not in found]
        for i, p in enumerate(todo):
            found[p] = simulate_plan(horse, M, p[0], p[1], p[2], max_budget, runs=runs[0], seed=seed,
                                     switch_at=p[3], **kw)
            if progress:
                progress(label, i + 1, len(todo))

    def promising():
        keep = {("at30", 1, 0, 0)}
        for B in range(max_budget + 1):
            for goal, margin in (("full", 0.03), ("wanted", 0.1)):     # ~2 standard errors at 1000 runs
                ok = [p for p in found if found[p][goal][B] is not None]
                ranked = sorted(ok, key=lambda p: -found[p][goal][B])
                keep.update(ranked[:top])
                close = [p for p in ranked if found[p][goal][B] >= found[ranked[0]][goal][B] - margin]
                keep.update(close[:max_close])
        return keep

    ts = lambda st: switch_ts if st == "coursier_switch" else [0]
    run_all([("at30", 1, 0, 0)] + [(st, lv, cap, T) for st in strategies for lv in levels for cap in caps
                                   for T in ts(st) if cap <= max_budget], "grid")
    if refine:
        near = set()
        for st, lv, cap, T in promising():
            if st in strategies:
                t2s = [t for t in (T - 1, T, T + 1) if t in SWITCH_TS] if st == "coursier_switch" else [0]
                near.update((st, l2, c2, t2) for l2 in _neighbors(lv, levels, 1, max_level - 1)
                            for c2 in _neighbors(cap, caps, 1, max_budget) for t2 in t2s)
        run_all(sorted(near), "refine")
    if stage1 is not None:
        stage1.update(found)
    final = promising() | {rule_plan(B, kw.get("start_level", 1), kw.get("wanted")) for B in range(max_budget + 1)}
    return {p: simulate_plan(horse, M, p[0], p[1], p[2], max_budget, runs=runs[1], seed=seed + 1000,
                             switch_at=p[3], **kw)
            for p in sorted(final)}


def suggested_plan(res, B, margin=0.01, start_level=1, always_best=False, wanted=None, safe_margin=0.0,
                   cheaper=None):
    """One plan to follow for budget B (full-set goal): the general rule's plan if it's within margin of the best
    plan in res, else the best (always the best with always_best). With safe_margin (and tails in res), 'the best'
    is, among the plans within safe_margin of the top full-set chance, the one most likely to miss at most 1 wanted
    skill; among those also within safe_margin of that, the one using the fewest coupons (when used is in res). With cheaper (and used in res): not the rule's plan when another plan is at least as likely to give the
    full set and uses at least `cheaper` fewer coupons on average ('cheaper': the best is suggested).
    Returns (plan, 'rule', 'best' or 'cheaper', the rule plan's chance or None)."""
    top = tied_plans(res, B, "full", safe_margin)
    best = top[0]
    if safe_margin and all(res[p].get("tails") for p in top):
        safest = max(res[p]["tails"][B][1] for p in top)
        safe = [p for p in top if res[p]["tails"][B][1] >= safest - safe_margin]
        if all(res[p].get("used") for p in safe):              # tied on both: the one using the fewest coupons
            best = min(safe, key=lambda p: (round(res[p]["used"][B], 9), -res[p]["full"][B]))
        else:
            best = max(safe, key=lambda p: (round(res[p]["tails"][B][1], 9), res[p]["full"][B]))
    rp = rule_plan(B, start_level, wanted)
    rc = res[rp]["full"][B] if rp in res and res[rp]["full"][B] is not None else None
    if not always_best and rc is not None and rc >= res[top[0]]["full"][B] - margin:
        ru = res[rp].get("used") and res[rp]["used"][B]
        if cheaper is None or ru is None or not any(
                res[p]["full"][B] is not None and res[p]["full"][B] >= rc and res[p].get("used")
                and res[p]["used"][B] <= ru - cheaper for p in res):
            return rp, "rule", rc
        return best, "cheaper", rc
    return best, "best", rc



FRONTIER_TOL = (0.003, 0.03, 0.003)     # full set, coupons used, stuck: about the noise at 20,000 horses


def _beats(b, a, tol):
    """b beats a within noise: no worse than a by more than tol on any criterion (full set higher, coupons used and
    stuck lower), and better by more than tol on at least one."""
    if b[0] < a[0] - tol[0] or b[1] > a[1] + tol[1] or b[2] > a[2] + tol[2]:
        return False
    return b[0] > a[0] + tol[0] or b[1] < a[1] - tol[1] or b[2] < a[2] - tol[2]


def frontier(res, N, tol=FRONTIER_TOL, learned_count=0, start_level=1):
    """The plans of res that no other plan beats within noise (see _beats) on the three criteria with N coupons:
    the full-set chance, the expected coupons used, the stuck share. One plan per effective plan (effective_plan)
    and per near-identical result (within tol on all three), the higher full-set chance kept. Highest chance first.
    res: results with full, used and stuck (horses_fast.Evaluator.plans(used=True) or simulate_plan)."""
    pts = {p: (res[p]["full"][N], res[p]["used"][N], res[p]["stuck"]) for p in res
           if res[p]["full"][N] is not None}
    keep = [p for p in pts if not any(_beats(pts[q], pts[p], tol) for q in pts if q != p)]
    out, seen = [], set()
    for p in sorted(keep, key=lambda p: (-pts[p][0], pts[p][1], p)):
        e = effective_plan(p, learned_count, start_level)
        if e in seen or any(all(abs(pts[p][i] - pts[q][i]) <= tol[i] for i in range(3)) for q in out):
            continue
        seen.add(e)
        out.append(p)
    return out


def frontier_candidates(stage1, N, tol=(0.01, 0.1, 0.01), most=30):
    """Plans worth rechecking for the frontier, from noisier values (e.g. 1,000 horses): those that no other plan
    clearly beats (at least as good on all three criteria, and better by more than tol on one), the `most` best of
    them by each criterion (full set, coupons used, stuck), and at30."""
    pts = {p: (r["full"][N], r["used"][N], r["stuck"]) for p, r in stage1.items()
           if r.get("used") and r["full"][N] is not None}

    def clearly(b, a):
        return (b[0] >= a[0] and b[1] <= a[1] and b[2] <= a[2]
                and (b[0] > a[0] + tol[0] or b[1] < a[1] - tol[1] or b[2] < a[2] - tol[2]))
    order = sorted(pts, key=lambda p: (-pts[p][0], pts[p][1], p))
    keep = [p for p in order if not any(clearly(pts[q], pts[p]) for q in order if q != p)]
    picks = []
    for k in ((lambda p: (-pts[p][0], pts[p][1])), (lambda p: (pts[p][1], -pts[p][0])),
              (lambda p: (pts[p][2], -pts[p][0]))):
        picks += sorted(keep, key=k)[:most]
    return list(dict.fromkeys(picks + [("at30", 1, 0, 0)]))


def tied_plans(res, B, goal, margin):
    """Plans within margin of the best for budget B (goal 'full' or 'wanted'), best first."""
    ok = [p for p in res if res[p][goal][B] is not None]
    best = max(res[p][goal][B] for p in ok)
    return sorted((p for p in ok if res[p][goal][B] >= best - margin), key=lambda p: -res[p][goal][B])


def describe_plans(plans, budget, learned_count=0, start_level=0):
    """Short text for a set of tied plans: per strategy, the span of start levels, of coupons kept, and for
    coursier_switch of the threshold. Plans in their effective form (see effective_plan)."""
    plans = list(dict.fromkeys(effective_plan(p, learned_count, start_level) for p in plans))
    parts, seen = [], []
    for p in plans:
        if p[0] not in seen:
            seen.append(p[0])
    for st in seen:
        ps = [p for p in plans if p[0] == st]
        if st == "at30":
            parts.append("at30")
            continue
        lv = sorted({p[1] for p in ps})
        kp = sorted({budget - p[2] for p in ps})
        span = lambda v: f"{v[0]}" if v[0] == v[-1] else f"{v[0]}-{v[-1]}"
        if st == "coursier_switch":
            Ts = sorted({p[3] for p in ps})
            parts.append(f"from lvl {span(lv)}, S1 until {span(Ts)} learned skills, then S2, keep {span(kp)}")
        else:
            parts.append(f"{PLAN_LABEL.get(st, st)}: from lvl {span(lv)}, keep {span(kp)}")
    return " | ".join(parts)
