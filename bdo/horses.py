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
BOXES = {"none": (0, 0), "gear": (1, 0), "brand": (0, 1), "both": (1, 1)}

# Default wanted list: skills for travel. Skills a horse can't learn are ignored.
TRAVEL_SET = ["Sprint", "Instant Accel", "S: Instant Accel", "Drift", "High Jump", "Streak Leap", "Start Accel",
              "Quick Ride", "Charge", "Sideways", "S: Sideways", "Quick Back", "Quick Stop",
              # Dream / Mythical / Voltarion skills that can be learned (not innate)
              "Wings of Freedom", "Earth of Protection", "Dark Sprint", "Lightning Charge",
              "Instant Accel: Flash", "Drift: Flash", "Thunderfall"]
CLASSIC_FODDER = ["Hind Kick", "Fore Chop"]
STRATEGIES = ["natural", "at30", "coursier", "hard", "ideal"]
STRATEGY_HELP = {
    "natural": "no coupons used",
    "at30": "level naturally, spend all coupons at level 30 on unwanted skills",
    "coursier": "swap Hind Kick/Fore Chop each time they're learned (keeping a reserve), rest at 30",
    "hard": "swap every unwanted skill until a wanted one comes (keeping a reserve), rest at 30",
    "ideal": "upper bound: unlimited coupons, always holding the rarest skills",
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

    Headers: name, training (e.g. Artisan 7), boxes (none/gear/brand/both), learned (skills marked learned or
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
        raise DataError("the reading needs a 'none' row above 0% (take it at a lower Training level, without boxes)")
    gear, brand = BOXES[meta.get("boxes", "none").lower()]
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
             point_bonus=0.25, points=0, runs=5000, seed=1, max_level=30, reserve=0):
    """Monte Carlo of leveling start_level -> max_level. Returns averages over runs.

    reserve: coupons the coursier/hard strategies keep for the level-30 cleanup (no swaps while leveling below it).
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
            elif strategy == "coursier":
                for s in fodder:
                    if s in have and c > reserve:
                        swap(s)
            elif strategy == "hard":
                for s in sorted(have - wanted, key=lambda s: -wt[s]):
                    if s in have and c > reserve:
                        slot = s
                        while slot not in wanted and c > reserve:
                            slot = swap(slot)
                            if slot is None:
                                break
        if strategy in ("at30", "coursier", "hard"):
            for s in sorted(have - wanted, key=lambda s: -wt[s]):
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
