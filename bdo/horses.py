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
  the desired skill's weight is multiplied by (1 + point_bonus * Skill Change Points).
"""
import json
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
CLASSIC_FODDER = ["Hind Kick", "Fore Chop"]
STRATEGIES = ["natural", "at30", "coursier", "once", "hard", "ideal"]
STRATEGY_HELP = {
    "natural": "no coupons used",
    "at30": "level naturally, spend all coupons at level 30 on unwanted skills",
    "coursier": "swap Hind Kick/Fore Chop each time they're learned (keeping a reserve), rest at 30",
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
        if compact(key) == want:
            return Horse(key, h["weights"], h["no_skill_weight"], h["born_with"], h.get("tier"), h.get("source", ""),
                         h.get("date", ""), h.get("no_skill_weight_note", ""))
    raise DataError(f"unknown horse {name!r}; known: {', '.join(data['horses'])}")


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

    Headers: name, training (e.g. Artisan 7), boosts (none/gear/brand/both; 'boxes' also accepted), learned (skills marked learned or
    'base skill', comma-separated). Needs a 'none' row (Compétence non apprise) above 0%.
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
    learned = [resolve(s) for s in meta.get("learned", "").split(",") if s.strip()]
    w = {resolve(k): v / M for k, v in rows.items() if compact(k) not in (compact("none"), compact("Compétence non apprise"))}
    # normalise so that (sum of unlearned weights + W) = 100 at the reading
    W = 100 - sum(w.values())
    return Horse(meta.get("name", os.path.basename(path)), w, W, learned, source=f"simulator reading ({path})",
                 date=meta.get("date", ""))


# --- simulation ----------------------------------------------------------------------------------------------

def _draw(rng, items, weights):
    x = rng.random() * sum(weights)
    for s, w in zip(items, weights):
        x -= w
        if x < 0:
            return s
    return items[-1] if items else None


def simulate(horse, M, strategy, coupons=30, tickets=0, start_level=1, learned=(), wanted=None, fodder=None,
             point_bonus=0.25, points=0, runs=5000, seed=1, max_level=30, reserve=0, swap_from=1):
    """Monte Carlo of leveling start_level -> max_level. Returns averages over runs.

    reserve: coupons the coursier/once/hard strategies keep for the level-30 cleanup (no swaps while leveling below it).
    swap_from: horse level from which coursier/once/hard start swapping while leveling (before it, they wait).
    """
    rng = random.Random(seed)
    pool = list(horse.weights)
    wt = horse.weights
    wanted = set(TRAVEL_SET if wanted is None else wanted) & set(pool)
    fodder = [s for s in (CLASSIC_FODDER if fodder is None else fodder) if s in wt and s not in wanted]
    rare = sorted(pool, key=lambda s: wt[s])
    tot_sum = wanted_sum = all_count = used_sum = 0
    for _ in range(runs):
        have = set(s for s in learned if s in wt)
        c = 0 if strategy == "natural" else coupons
        t, pts = tickets, points

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
            pts += 1
            return new

        def fix(slot):                               # re-swap a slot until it holds a wanted skill
            while slot not in wanted and c > 0:
                new = swap(slot)
                if new is None:
                    return
                slot = new

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
            if strategy == "ideal":
                have = set(rare[:len(have)])
            elif _lvl + 1 < swap_from:                 # level just reached is below swap_from: no swaps yet
                pass
            elif strategy == "coursier":
                for s in fodder:
                    if s in have and c > reserve:
                        swap(s)
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
        if strategy in ("at30", "coursier", "once", "hard"):
            # level-30 cleanup, rarest unwanted skill first: a swapped-away skill goes back into the coupon draw,
            # so common ones (Hind Kick...) are kept until last to keep their big weight out of the other swaps
            for s in sorted(have - wanted, key=lambda s: wt[s]):
                if s in have:
                    fix(s)
        n = len(have)
        nw = min(n, len(wanted)) if strategy == "ideal" else len(have & wanted)
        tot_sum += n
        wanted_sum += nw
        all_count += nw == len(wanted)
        used_sum += 0 if strategy in ("natural", "ideal") else coupons - c
    return {"skills": tot_sum / runs, "wanted": wanted_sum / runs, "all_wanted": all_count / runs,
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
# A plan = (strategy, swap_from, spend_cap): swap while leveling from level swap_from on, spending at most spend_cap
# coupons, then do the level-30 cleanup with whatever is left. For a budget B >= spend_cap this is the same as
# "keep B - spend_cap coupons for level 30". One simulation of a plan gives its result for every budget at once:
# the cleanup is run with as many coupons as it takes, and a budget B simply stops it after B coupons in total.

def simulate_plan(horse, M, strategy, swap_from=1, spend_cap=0, max_budget=60, tickets=0, start_level=1, learned=(),
                  wanted=None, fodder=None, point_bonus=0.25, points=0, runs=4000, seed=1, max_level=30):
    """Monte Carlo of one plan for every budget 0..max_budget.

    Returns a dict: full[B] (chance of every wanted skill with B coupons), wanted[B] (average wanted skills),
    for B >= spend_cap (None below); skills (average skills at 30, budget-independent); needed (sorted coupons
    needed per run for the full set, inf when the horse has too few skills); skill_counts (sorted, per run).
    """
    rng = random.Random(seed)
    pool = list(horse.weights)
    wt = horse.weights
    wanted = set(TRAVEL_SET if wanted is None else wanted) & set(pool)
    fodder = [s for s in (CLASSIC_FODDER if fodder is None else fodder) if s in wt and s not in wanted]
    if strategy == "at30":
        spend_cap = 0
    nb = max_budget + 1
    full_n, wanted_sum = [0] * nb, [0] * nb
    needed, counts = [], []
    for _ in range(runs):
        have = set(s for s in learned if s in wt)
        spent, t, pts = 0, tickets, points

        def swap(out):
            nonlocal spent, pts
            cands = [s for s in pool if s not in have and s != out]
            if not cands:
                return None
            target = min((s for s in wanted if s in cands), key=lambda s: wt[s], default=None)
            ws = [wt[s] * (1 + point_bonus * pts) if s == target else wt[s] for s in cands]
            new = _draw(rng, cands, ws)
            have.discard(out)
            have.add(new)
            spent += 1
            pts += 1
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
                t -= 1
            if got:
                have.add(got)
            if _lvl + 1 < swap_from or spent >= spend_cap:
                continue
            if strategy == "coursier":
                for s in fodder:
                    if s in have and spent < spend_cap:
                        swap(s)
            elif strategy == "once":
                todo = sorted(have - wanted, key=lambda s: wt[s]) if _lvl + 1 == swap_from > 1 else [got]
                for s in todo:
                    if s and s not in wanted and s in have and spent < spend_cap:
                        swap(s)
            elif strategy == "hard":
                for s in sorted(have - wanted, key=lambda s: wt[s]):
                    slot = s
                    while slot is not None and slot not in wanted and slot in have and spent < spend_cap:
                        slot = swap(slot)
        counts.append(len(have))
        base = spent
        traj = [len(have & wanted)]                  # wanted skills after 0, 1, 2... cleanup coupons
        if strategy != "natural":
            for s in sorted(have - wanted, key=lambda s: wt[s]):     # rarest unwanted first (see simulate)
                slot = s
                while slot is not None and slot not in wanted and not wanted <= have:
                    slot = swap(slot)
                    traj.append(len(have & wanted))
                if wanted <= have:
                    break
        need = base + len(traj) - 1 if wanted <= have else float("inf")
        needed.append(need)
        last = len(traj) - 1
        for B in range(spend_cap, nb):
            j = B - base
            if strategy == "natural":
                j = 0
            wanted_sum[B] += traj[min(j, last)]
            full_n[B] += need <= B if strategy != "natural" else traj[0] == len(wanted)
    needed.sort()
    counts.sort()
    return {"full": [full_n[B] / runs if B >= spend_cap else None for B in range(nb)],
            "wanted": [wanted_sum[B] / runs if B >= spend_cap else None for B in range(nb)],
            "skills": sum(counts) / runs, "needed": needed, "skill_counts": counts, "wanted_total": len(wanted)}


def percentile(sorted_values, p):
    """Value below which a share p (0-1) of the sorted values falls (nearest rank)."""
    if not sorted_values:
        return None
    i = min(len(sorted_values) - 1, max(0, int(round(p * len(sorted_values) + 0.5)) - 1))
    return sorted_values[i]


PLAN_LEVELS = [1, 4, 7, 10, 13, 16, 18, 20, 22, 24, 26, 28]
PLAN_CAPS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30]


def plan_name(plan, budget=None):
    st, lv, cap = plan
    if st in ("at30", "natural"):
        return st
    keep = f", keep {budget - cap}" if budget is not None else ""
    return f"{st} from lvl {lv}, spend <= {cap}{keep}"


def optimize(horse, M, max_budget=50, strategies=("coursier", "once", "hard"), levels=None, caps=None,
             runs=(1000, 6000), top=6, seed=1, progress=None, **kw):
    """Search plans for every budget 0..max_budget, for two goals: 'full' (chance of every wanted skill) and
    'wanted' (average wanted skills). Stage 1: every plan of the grid with runs[0]. Stage 2: for each budget and
    goal, the top plans of stage 1 again with runs[1] and a fresh seed (to avoid picking a lucky winner).
    Returns {plan: simulate_plan result} for the stage-2 plans."""
    levels = PLAN_LEVELS if levels is None else levels
    caps = PLAN_CAPS if caps is None else caps
    plans = [("at30", 1, 0)] + [(st, lv, cap) for st in strategies for lv in levels for cap in caps
                                if cap <= max_budget]
    stage1 = {}
    for i, p in enumerate(plans):
        stage1[p] = simulate_plan(horse, M, p[0], p[1], p[2], max_budget, runs=runs[0], seed=seed, **kw)
        if progress:
            progress(i + 1, len(plans))
    keep = {("at30", 1, 0)}
    for B in range(max_budget + 1):
        for goal in ("full", "wanted"):
            ok = [p for p in plans if stage1[p][goal][B] is not None]
            keep.update(sorted(ok, key=lambda p: -stage1[p][goal][B])[:top])
    return {p: simulate_plan(horse, M, p[0], p[1], p[2], max_budget, runs=runs[1], seed=seed + 1000, **kw)
            for p in sorted(keep)}
