#!/usr/bin/env python3
"""Regression tests for every tool (live API calls). Run before every push:

    python3 -I tests/run_all.py

Prints one line per check and 'ALL OK' at the end; exit code 1 if anything failed.
Expect ~1-2 min (Arsha retries can make it slower; the horse optimizer checks take ~45 s with numba).
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failures = 0


def run(*args):
    p = subprocess.run([sys.executable, "-I", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return p.returncode, p.stdout + p.stderr


def check(name, cond, out=""):
    global failures
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        failures += 1
        print("     output:", out[:800].replace("\n", "\n     "))


# --- prices.py ---------------------------------------------------------------
code, out = run("prices.py", "Vell's Heart", "4998", "Silver Ingot", "Gold Bar 1,000G",
                "Advice of Valks (+300) Box", "Vells Hart", "Urugon's Shoes", "999999999", "--sid", "0", "--tax")
check("prices: exit code 2 (deliberate bad inputs)", code == 2, out)
check("prices: Vell's Heart priced with basis", re.search(r"^45332\tVell's Heart\t[\d,]+\t[\d,]+\t(last sale|\d+-day avg)", out, re.M), out)
check("prices: shard priced", re.search(r"^4998\tSharp Black Crystal Shard\t[\d,]+", out, re.M), out)
check("prices: Silver Ingot same-name note + row", "SAME NAME, 2 IDs - hid untradeable" in out and re.search(r"^4252\tSilver Ingot\t[\d,]+", out, re.M), out)
check("prices: gold bar fixed, untaxed", "5\tGold Bar 1,000G\t10,000,000\t10,000,000\tfixed NPC value" in out, out)
check("prices: Valks box NOT ON MARKET", re.search(r"^860139\t.*NOT ON MARKET", out, re.M), out)
check("prices: typo suggests Vell's Heart", "NOT FOUND" in out and "Vell's Heart (id 45332)" in out, out)
check("prices: Urugon's Shoes one priced row", re.search(r"^11103\tUrugon's Shoes\t[\d,]+", out, re.M), out)
check("prices: unknown id", re.search(r"^999999999\t.*UNKNOWN ID", out, re.M), out)

code, out = run("prices.py", "--avg", "30", "4998")
check("prices --avg 30", code == 0 and re.search(r"30-day avg to \d{4}-\d\d-\d\d", out), out)
code, out = run("prices.py", "--latest", "4998", "--details")
check("prices --latest --details", code == 0 and "last sale" in out and "\tmax\t" in out, out)

# --- items.py ----------------------------------------------------------------
code, out = run("items.py", "Vell's Heart", "4998", "Vells Hart")
check("items: resolve + typo", code == 2 and "45332\tVell's Heart" in out and "4998\tSharp Black Crystal Shard" in out and "NOT FOUND" in out, out)
code, out = run("items.py", "--search", "Dehkia's Artifact")
check("items --search", code == 0 and "748022\tDehkia's Artifact - All Evasion" in out, out)

# --- languages and loose matching (both tools share bdo/items.py) -------------
code, out = run("items.py", "--lang", "fr", "Coeur de Vell", "eclat de cristal noir tranchant", "Lingot d'or 1000G")
check("items --lang fr: oe, accents, spaces", code == 0 and "45332\tCœur de Vell" in out
      and "4998\tÉclat de cristal noir tranchant" in out and "5\tLingot d'or 1 000 G" in out, out)
code, out = run("items.py", "Vells Heart", "Hashashin BD9 Armor N")
check("items: compact match; loose match on different names refused", "45332\tVell's Heart" in out and code == 2 and re.search(r"Hashashin BD9 Armor N\tNOT FOUND.*BD9\+ Armor N", out), out)
code, out = run("items.py", "--lang", "en,fr", "Vell's Heart", "Pierre de Caphras")
check("items --lang en,fr: both columns, either language", code == 0 and out.startswith("id\tname_en\tname_fr\tnote")
      and "45332\tVell's Heart\tCœur de Vell" in out and "721003\tCaphras Stone\tPierre de Caphras" in out, out)
code, out = run("items.py", "--lang", "en,fr", "--search", "coeur de vell")
check("items --search in French", code == 0 and "45332\tVell's Heart\tCœur de Vell" in out, out)
code, out = run("items.py", "--lang", "xx", "4998")
check("items: unknown language", code == 2 and "UNKNOWN LANGUAGE" in out, out)
code, out = run("prices.py", "--lang", "fr", "Coeur de Vell", "4998")
check("prices --lang fr", code == 0 and re.search(r"^45332\tCœur de Vell\t[\d,]+", out, re.M)
      and re.search(r"^4998\tÉclat de cristal noir tranchant\t[\d,]+", out, re.M), out)
code, out = run("prices.py", "--lang", "en,fr", "Pierre de Caphras")
check("prices --lang en,fr", code == 0 and re.search(r"^721003\tCaphras Stone\tPierre de Caphras\t[\d,]+", out, re.M), out)
code, out = run("prices.py", "--lang", "xx", "4998")
check("prices: unknown language", code == 2 and "UNKNOWN LANGUAGE" in out, out)

# --- horse_skills.py (offline) -------------------------------------------------
# In-game growth simulator readings (2026-11-17): the model must reproduce them.
D = "Mythical Diné"
for args, obs in [
    (["--training", "Artisan 7"], ["Ruade=15.1844", "none=10.7826", "Accél. Fulgurante=1.4554"]),
    (["--training", "Professionnel 10"], ["Ruade=14.5731", "none=14.3746"]),
    (["--training", "Artisan 7", "--brand"], ["Ruade=16.4321", "none=3.4516"]),
    (["--training", "Artisan 7", "--gear", "--brand"], ["Ruade=17.0196", "none=0"]),       # cap
    (["--training", "Gourou 57"], ["Ruade=17.0194", "none=0"]),
    (["--training", "Artisan 7", "--learned", "Saut haut"], ["Ruade=15.6382", "none=11.7532"]),
]:
    code, out = run("horse_skills.py", D, *args, "--check", *obs)
    check(f"horse_skills --check {' '.join(args)}", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Professional 10", "--check",
                "none=27.3544", "Ruade=10.5304", "Accél. Fulgurante=1.6668")
check("horse_skills --check T8", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "Doom (T9)", "--training", "Artisan 7", "--check", "none=2.8289", "Deux places=3.7851", "Galop funeste=2.7253")
check("horse_skills --check T9 Doom", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "Doom (T9)", "--training", "Artisan 8", "--check", "none=2.27", "Ruade=20.4222",
                "S : Pas latéraux=0.1936", "S : Charge=6.8524", "Galop funeste=2.741")
check("horse_skills --check T9 Doom, Artisan 8 reading (refined weights)", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Artisan 8", "--check", "none=23.8715",
                "Ruade=11.0353", "S : Pas latéraux=0.2656", "Deux places=1.0622", "Prudence=4.06")
check("horse_skills --check T8 'Choky', Artisan 8 reading (refined weights)", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--check", "Ruade=16")
check("horse_skills --check mismatch exits 1", code == 1 and "MISMATCH" in out, out)
code, out = run("horse_skills.py", "--horse-file", "tests/data/sim_mythical_dine_artisan7.csv", "--training", "Professional 10",
                "--check", "Ruade=14.5731", "none=14.3746")
check("horse_skills --horse-file (simulator reading)", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--runs", "300", "--coupons", "20")
rows = {l.split("\t")[0]: l.split("\t") for l in out.splitlines() if not l.startswith("#")}
ok = code == 0 and set(rows) >= {"natural", "at30", "coursier", "coursier_v2", "coursier_switch", "hard", "ideal"}
if ok:
    first = lambda r, i: float(r[i].split("/")[0].rstrip("%"))
    ok = first(rows["ideal"], 2) >= first(rows["coursier"], 2) >= first(rows["natural"], 2)
check("horse_skills simulation table", ok, out)
code, out = run("-c", "import sys; sys.path.insert(0, '.'); from bdo import horses as H; c = H.COURSER_SET; "
                "print(H.rule_plan(1), H.rule_plan(6), H.rule_plan(6, wanted=c), H.rule_plan(2, wanted=c), "
                "H.rule_plan(9), H.rule_plan(15), H.rule_plan(24), H.rule_plan(25), H.rule_plan(30, wanted=c), "
                "H.rule_plan(20, start_level=15))")
check("rule_plan: the compact rules (1 / 2-24 V2 / 25+ switch; courser starts 2-6), halves rounded up, partway horse",
      code == 0 and out.strip() == "('at30', 1, 0, 0) ('coursier_v2', 21, 5, 0) ('coursier_v2', 18, 5, 0) "
      "('coursier_v2', 26, 1, 0) ('coursier_v2', 15, 8, 0) ('coursier_v2', 10, 14, 0) ('coursier_v2', 10, 23, 0) "
      "('coursier_switch', 10, 24, 12) ('coursier_switch', 10, 24, 12) ('coursier_v2', 16, 19, 0)", out)
code, out = run("-c", "import sys; sys.path.insert(0, '.'); from bdo import horses as H; "
                "h = H.get_horse(H.load_data(), 'T8 example (bdolytics icon horse_71)'); "
                "d = H.get_horse(H.load_data(), 'Mythical Diné'); "
                "print(H.CLASSIC_FODDER, H._cycle_skill(H.CLASSIC_FODDER, h.weights), "
                "H._cycle_skill(H.CLASSIC_FODDER, d.weights))")
check("V0 swaps Fore Chop first; V2 cycles the heavier fodder, Hind Kick on ties (T8)", code == 0 and out.strip() ==
      "['Fore Chop', 'Hind Kick'] Hind Kick Hind Kick", out)
# T8 types: every value of the in-game simulator readings (tests/data/sim_t8_types_2026-11-21.csv, default horses)
code, out = run("-c", """
import csv, re, sys; sys.path.insert(0, '.')
from bdo import horses as H
d = H.load_data(); res = H.skill_resolver(d); worst, n = 0, 0
rows = [r for r in csv.reader(l for l in open('tests/data/sim_t8_types_2026-11-21.csv') if not l.startswith('#'))][1:]
for reading, typ, tr, lvl, boosts, innate, skill, pct in rows:
    if reading.startswith('special') or pct == 'base':
        continue
    h = H.get_horse(d, 'T8 Type ' + typ); M = 1 + H.training_bonus(tr) / 100
    U = sum(h.weights.values()); T = U + h.W
    m = re.match(r'cut [(](.*)[)]', skill); name = m.group(1) if m else skill
    pred = 100 * (1 - M * U / T) if name == 'Compétence non apprise' else 100 * M * h.weights[res(name)] / T
    worst = max(worst, abs(pred - float(pct))); n += 1
print(worst < 0.002, n, round(worst, 4))
""")
check("T8 types (aliases too) reproduce every value of the simulator readings (within 0.002 points)",
      code == 0 and out.startswith("True"), out)
# the older readings (2026-11-17/18: Diné, T9 Doom, Choky at several Training levels and boosts, a learned skill)
code, out = run("-c", """
import csv, re, sys
sys.path.insert(0, '.')
from bdo import horses as H
d = H.load_data(); res = H.skill_resolver(d)
HORSE = {"Mythical Diné": "Mythical Diné", "T9 Doom": "Doom (T9)", "T8 Choky": "T8 Type 1"}
TR = {"Maître 20": "Master 20", "Gourou 57": "Guru 57", "Professionnel 10": "Professional 10"}
rows = [r for r in csv.reader(l for l in open('tests/data/sim_older_2026-11-17.csv') if not l.startswith('#'))][1:]
worst, n, bad = 0, 0, []
for reading, horse, tr, lvl, boosts, innate, skill, pct in rows:
    if pct in ("base", "learned") or "coupon" in reading or "not shown" in tr:
        continue
    h = H.get_horse(d, next(v for k, v in HORSE.items() if horse.startswith(k)))
    tr = TR.get(tr, tr).replace(" (inferred)", "")
    M = 1 + H.training_bonus(tr) / 100 + (0.10 if boosts.startswith(("gear", "brand")) else 0)
    w = dict(h.weights)
    if "High Jump learned" in innate:
        w.pop("High Jump")
    U = sum(w.values()); k = min(M / (U + h.W), 1 / U)
    m = re.match(r'cut [(](.*)[)]', skill); name = m.group(1) if m else skill
    pred = 100 * (1 - k * U) if name == 'Compétence non apprise' else 100 * k * w[res(name)]
    e = abs(pred - float(pct)); worst = max(worst, e); n += 1
    if e > 0.002: bad.append((reading, skill, pct, round(pred, 4)))
print(worst < 0.002, n, round(worst, 4), bad[:8])
""")
check("older simulator readings (tests/data/sim_older_2026-11-17.csv) reproduced within 0.002 points",
      code == 0 and out.startswith("True"), out)
code, out = run("horse_skills.py", "T8 Type 5", "--training", "Artisan 7", "--coupons", "10", "--strategy", "coursier_v2")
code2, out2 = run("horse_skills.py", D, "--training", "Artisan 7", "--coupons", "10", "--strategy", "coursier_v2")
code3, out3 = run("horse_skills.py", "T8 Type 5", "--training", "Artisan 7", "--coupons", "10", "--strategy",
                  "coursier_v2", "--wanted", "travel")
check("--wanted: courser set by default for a T8, travel for a T10, named sets accepted",
      code == 0 and "# wanted: courser set (the default for a T8" in out and "wanted: 6 skills" in out
      and code2 == 0 and "# wanted: travel set (the default for a T10" in out2
      and code3 == 0 and "# wanted: travel set\n" in out3 + "\n", out + out2 + out3)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--always-best")
check("horse_skills: --always-best without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--selection-coupon", "planned")
check("horse_skills: --selection-coupon without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("-c", """
import sys
sys.path.insert(0, ".")
from bdo import horses as H
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)"); M = h.M(7.1, 0, 0)
f = lambda c: H.simulate_plan(h, M, "coursier_v2", 10, 12, 20, runs=1500, seed=5, coupon=c)["full"][20]
print(f(None) + 0.1 < f("fallback") <= 1, f(None) + 0.1 < f("planned") <= 1)
""")
check("bdo.horses simulate_plan with a Selection Coupon (planned / fallback beat none)", code == 0 and out.strip() == "True True", out)
# Skill Change Points back to 0 when a coupon gives the desired skill: a 2-coupon case computed by hand
RESET_CASE = """
import math, sys
sys.path.insert(0, ".")
from bdo import horses as H
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)"); M = h.M(7.1, 0, 0)
wt = h.weights; pool = list(wt); r = lambda s: (wt[s], pool.index(s))
X, Y = sorted(set(H.TRAVEL_SET) & set(pool), key=r)[:2]
o1 = min((s for s in pool if s not in H.TRAVEL_SET), key=r)
learned = [s for s in pool if s not in (X, Y)]
# level 30, 20 points, every skill but the two rarest wanted ones X, Y; 2 coupons. Coupon 1 swaps the rarest unwanted
# skill o1, drawing X (desired, boosted) or Y. Coupon 2: if X came, the points are back to 0 and Y is drawn against o1
# unboosted; if Y came, 21 points boost X against o1.
b0, b1 = 1 + 0.25 * 20, 1 + 0.25 * 21
pX = wt[X] * b0 / (wt[X] * b0 + wt[Y])
second = (1 - pX) * wt[X] * b1 / (wt[X] * b1 + wt[o1])
exact = pX * wt[Y] / (wt[Y] + wt[o1]) + second
no_reset = pX * wt[Y] * b1 / (wt[Y] * b1 + wt[o1]) + second
"""
code, out = run("-c", RESET_CASE + """
N = 40000
a = H.simulate_plan(h, M, "at30", 1, 0, 2, runs=N, seed=9, start_level=30, learned=learned, points=20)["full"][2]
b = H.simulate(h, M, "at30", 2, runs=N, seed=9, start_level=30, learned=learned, points=20)["all_wanted"]
se = math.sqrt(exact * (1 - exact) / N)
print(abs(a - exact) < 4 * se, abs(b - exact) < 4 * se, no_reset - exact > 20 * se, round(exact, 4), round(a, 4), round(b, 4))
""")
check("bdo.horses: points reset on a desired hit (simulate_plan and simulate match a hand-computed 2-coupon case)",
      code == 0 and out.startswith("True True True"), out)
# coursier_switch with a threshold never reached is coursier, with 0 it's coursier_v2 (same random numbers)
code, out = run("-c", """
import sys
sys.path.insert(0, ".")
from bdo import horses as H
h = H.get_horse(H.load_data(), "Doom (T9)"); M = h.M(0, 0, 0)
f = lambda st, T: H.simulate_plan(h, M, st, 10, 15, 20, runs=300, seed=5, switch_at=T)["full"]
print(f("coursier_switch", 0) == f("coursier_v2", 0), f("coursier_switch", 99) == f("coursier", 0))
""")
check("coursier_switch limits: T=0 is coursier_v2, T never reached is coursier", code == 0 and out.strip() == "True True", out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--runs", "200", "--target", "50",
               "--strategy", "at30,coursier")
m = re.search(r"^coursier\t(\d+)/(\d+)/(\d+)$", out, re.M)
check("horse_skills --target (coupons needed)", code == 0 and m and all(10 <= int(x) <= 30 for x in m.groups())
      and re.search(r"^at30\t\d+/\d+/\d+$", out, re.M), out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--target", "0")
check("horse_skills: bad --target exits 2", code == 2 and "--target" in out, out)
code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Guru 20", "--optimize", "3")
m = re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M)
check("horse_skills --optimize", code == 0 and [b for b, _ in m] == ["0", "1", "2", "3"]
      and float(m[3][1]) >= float(m[0][1]) and "coupons for a 50%" in out, out)
code2, out2 = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Guru 20", "--optimize", "3",
                  "--always-best")
src2 = re.findall(r"^\d+\t(?:from lvl|no swaps).*\t(rule|best) \(", out2, re.M)
check("horse_skills --optimize --always-best: every suggested plan is the best found", code2 == 0 and src2 == ["best"] * 3
      and "--always-best" in out2, out2)
code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Guru 20", "--optimize", "2",
               "--engine", "python")
m = re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M)
check("horse_skills --optimize --engine python", code == 0 and [b for b, _ in m] == ["0", "1", "2"]
      and "plain-Python engine" in out, out)
# fast engine (needs numba; skipped otherwise): same model as the plain-Python one, so the same chances within noise
code, out = run("-c", "import sys; sys.path.insert(0, '.'); import bdo.horses_fast as F; print(F.available())")
if out.strip() == "True":
    code, out = run("-c", """
import math, sys
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "Mythical Diné"); M = h.M(21.7, 0, 0)
for st, L, cap, T in (("coursier_v2", 15, 9, 0), ("coursier", 20, 5, 0), ("at30", 1, 0, 0), ("coursier_switch", 8, 15, 11)):
    a = F.Evaluator(h, M, max_budget=20).plan(st, L, cap, runs=8000, seed=3, switch_at=T)["full"]
    b = H.simulate_plan(h, M, st, L, cap, 20, runs=4000, seed=3, switch_at=T)["full"]
    z = max(abs(a[B] - b[B]) / math.sqrt(b[B] * (1 - b[B]) / 4000 + a[B] * (1 - a[B]) / 8000) for B in (15, 20))
    print(st, round(z, 2), "OK" if z < 4 else "DIFF")
""")
    check("horses_fast agrees with bdo.horses (same plans, within noise)", code == 0 and "DIFF" not in out
          and out.count("OK") == 4, out)
    code, out = run("-c", """
import sys
import numpy as np
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "Doom (T9)"); ev = F.Evaluator(h, h.M(0, 0, 0), max_budget=20)
w, n, W, M = ev.args; lmask, wmask, fod, cyc, order, rare = ev.masks
g = lambda st, T: F._many30(3000, 7, w, n, W, M, st, 10, 15, 0, 1, lmask, wmask, fod, cyc, order, rare, 0.25, 0, 30, T)
same = lambda x, y: all(np.array_equal(p, q) for p, q in zip(x, y))
print(same(g(7, 0), g(6, 0)), same(g(7, 99), g(1, 0)))
""")
    check("horses_fast coursier_switch limits: T=0 is coursier_v2, T never reached is coursier",
          code == 0 and out.strip() == "True True", out)
    code, out = run("-c", RESET_CASE + """
from bdo import horses_fast as F
ev = F.Evaluator(h, M, max_budget=2, start_level=30, learned=learned, points=20)
f = ev.plan("at30")["full"][2]
print(abs(f - exact) < 1e-5, round(f, 6), round(exact, 6))
""")
    check("horses_fast: points reset on a desired hit (exact cleanup matches the hand-computed 2-coupon case)",
          code == 0 and out.startswith("True"), out)
    code, out = run("-c", RESET_CASE + """
from bdo import horses_fast as F
r = F.Evaluator(h, M, max_budget=8, start_level=30, learned=learned, points=20).plans([("at30", 1, 0, 0)], runs=10,
                                                                                    used=True)[("at30", 1, 0, 0)]
u, f = r["used"], r["full"]
print(u[0] == 0 and all(abs(u[B] - u[B - 1] - (1 - f[B - 1])) < 1e-5 for B in range(1, 9)), u[2], u[8])
""")
    check("horses_fast used[B]: expected coupons used (the cleanup goes on while the set isn't full: "
          "used[B] - used[B - 1] = 1 - full[B - 1])", code == 0 and out.startswith("True 2.0"), out)
    code, out = run("-c", """
import math, sys
sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "Doom (T9)"); M = h.M(0, 0, 0)
for p, cp in ((("coursier", 10, 6, 0), None), (("at30", 1, 0, 0), "fallback")):
    a = F.Evaluator(h, M, max_budget=25).plans([p], runs=20000, seed=3, used=True, coupon=cp)[p]["used"]
    b = H.simulate_plan(h, M, *p[:3], 25, runs=4000, seed=4, coupon=cp)["used"]
    print(all(abs(a[B] - b[B]) < 4 * B / 2 / math.sqrt(4000) for B in (10, 25)), [round(a[B], 2) for B in (10, 25)],
          [round(b[B], 2) for B in (10, 25)])
""")
    check("horses_fast used[B] agrees with bdo.horses simulate_plan (within noise)",
          code == 0 and out.count("True") == 2, out)
    code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Skilled 1", "--optimize", "20",
                    "--wanted", "travel")
    m = dict(re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M))
    check("horse_skills --optimize: coursier_switch best at 20 coupons on a hard case (T8 Skilled 1, about 61%)",
          code == 0 and 56 <= float(m.get("20", 0)) <= 66
          and re.search(r"^20\t[\d.]+%\tcoursier_switch: from lvl \d+(-\d+)?, V0 until", out, re.M), out)
    lv = {int(l.split("\t")[0]): [float(x) for x in l.split("\t")[1:]] for l in out.split("# Average learned")[-1].splitlines()
          if re.match(r"^\d+\t[\d.]+", l)}
    check("horse_skills --optimize: average learned skills per level (levels 1-30, rising, ~13-16 at 30 on the T8 Skilled 1)",
          sorted(lv) == list(range(1, 31)) and all(lv[L][0] <= lv[L + 1][0] for L in range(1, 30))
          and all(12 <= x <= 16 for x in lv[30]), out[-1500:])
    sug = re.search(r"^20\t(from lvl \d+, V[02] until [^\t]+, keep \d+)\t([\d.]+)%\t([\d.]+)%\t"
                    r"([\d.]+)%\t(\d)\t[\d.]+\t[\d.]+\t(rule \(best ([\d.]+)%\)|best)", out, re.M)
    check("horse_skills --optimize: suggested plan per budget (20 coupons, rechecked with fresh horses: within 1 point "
          "of the best, and below the search's lucky best + 0.5; full set <= missing 1 <= missing 2)",
          sug is not None and (sug.group(7) is None or float(sug.group(2)) >= float(sug.group(7)) - 1.0)
          and float(sug.group(2)) <= float(m.get("20", 0)) + 0.5
          and float(sug.group(2)) <= float(sug.group(3)) <= float(sug.group(4)), out)
    sugrow = lambda o, B: next((l.split("\t") for l in o.splitlines() if l.startswith(f"{B}\tfrom lvl")), None)
    pct = lambda x: float(x.rstrip("%"))
    T8 = "T8 example (bdolytics icon horse_71)"
    code, out = run("horse_skills.py", T8, "--training", "Skilled 1", "--optimize", "12", "--selection-coupon", "planned")
    code0, out0 = run("horse_skills.py", T8, "--training", "Skilled 1", "--optimize", "12")
    r, r0 = sugrow(out, 12), sugrow(out0, 12)
    check("--selection-coupon planned: full set with it well above without (T8 Skilled 1, 12 coupons)",
          code == 0 and "Selection Coupon PLANNED" in out and r and r0 and pct(r[2]) >= pct(r0[2]) + 15, out + out0)
    code, out = run("horse_skills.py", T8, "--training", "Skilled 1", "--optimize", "12", "--selection-coupon", "fallback",
                    "--tickets", "2")
    rows = [sugrow(out, B) for B in (8, 10, 12)]
    check("--selection-coupon fallback and --tickets: extra columns (with the coupon >= without; keeping the tickets "
          "<= using them, within noise)", code == 0 and all(rows) and all(pct(x[8]) >= pct(x[2]) and pct(x[9]) <= pct(x[2]) + 1
                                                            for x in rows), out)
    code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--optimize", "10", "--engine", "numba")
    m = dict(re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M))
    code2, out2 = run("horse_skills.py", D, "--training", "Artisan 7", "--optimize", "10", "--engine", "numba", "--low-memory")
    m2 = dict(re.findall(r"^(\d+)\t([\d.]+)%\t", out2, re.M))
    check("horse_skills --optimize --low-memory: same best chances (16-bit values)", code2 == 0 and len(m2) == 11
          and all(abs(float(m2[b]) - float(m.get(b, -9))) <= 0.11 for b in m2), out2)
    check("horse_skills --optimize --engine numba (coursier_v2 best at 10 coupons, about 62%)",
          code == 0 and "fast engine" in out and 55 <= float(m.get("10", 0)) <= 70
          and re.search(r"^10\t[\d.]+%\tcoursier_v2", out, re.M), out)
    # --coupons-used and the effective plan, on the state of the 2026-11-21 live chat (T8 Type 6, 15 learned skills,
    # every skill left to learn wanted)
    T6L = ("Hind Kick,Fore Chop,Drift,Start Accel,High Jump,Quick Stop,Charge,Quick Back,Streak Leap,Roar,Caution,"
           "Quick Ride,S: Hind Kick,S: Fore Chop,S: Sideways")
    code, out = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--gear", "--level", "19", "--learned",
                    T6L + ",Sprint", "--optimize", "5", "--coupons-used", "2,3", "--lang", "fr")
    sug = {l.split("\t")[0]: l.split("\t") for l in out.split("# Coupons used")[0].splitlines()
           if re.match(r"^[1-5]\t(from|no swaps)", l)}
    am = {int(l.split("\t")[0]): [pct(x) for x in l.split("\t")[1:]] for l in out.split("at most B coupons\t")[-1].splitlines()
          if re.match(r"^\d+\t[\d.]+%", l)}
    check("horse_skills --coupons-used: at a plan's own budget, 'at most B coupons' is its full-set chance; rising",
          code == 0 and len(sug) == 5 and am and am[2][0] == pct(sug["2"][2]) and am[3][1] == pct(sug["3"][2])
          and all(am[B][j] <= am[B + 1][j] for B in range(len(am) - 1) for j in (0, 1)), out)
    check("horse_skills --coupons-used: spread table (average, median, 90% / 99%), used and per full set columns",
          re.search(r"^plan for 2 coupons\t[\d.]+\t\d+\t\d+\t\d+\t[\d.]+%$", out, re.M)
          and all(abs(float(sug[B][6]) / float(sug[B][7]) - pct(sug[B][2]) / 100) < 0.01 for B in sug), out)
    check("horse_skills: effective plan (a switch threshold already reached prints as V2), alias as typed, in-game "
          "count, French names in learned:, sure-hit note, innate skill in --learned ignored with a note",
          "V0 until 9 learned" not in out and "T8 Type 6 (an alias of T8 Type 4" in out
          and "learned: 15 + 1 innate (Sprint) = 16 in game: Ruade, Cabrade" in out
          and "every skill left to learn is wanted (" in out and "ignoring 'Sprint' in --learned: innate" in out, out)
    code, out = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--gear", "--level", "19", "--learned",
                    T6L, "--optimize", "5", "--fewest-coupons")
    fw = [l.split("\t") for l in out.split("# Fewest coupons until")[-1].splitlines() if re.match(r"^(from|no swaps)", l)]
    check("horse_skills --fewest-coupons: plans by average coupons until the full set, fewest first, at30 listed, "
          "one row per effective plan; 2-coupon suggestion rechecked: from lvl 24 (the 4,000-horse pick was 25)",
          code == 0 and len(fw) >= 3 and [float(x[1]) for x in fw] == sorted(float(x[1]) for x in fw)
          and fw[-1][0].startswith("no swaps") and len({x[0] for x in fw}) == len(fw)
          and "until 9 learned" not in out and re.search(r"^2\tfrom lvl 24, V0 until lvl 30, keep 1\t", out, re.M), out)
    code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H
r = {("a", 1, 1, 0): {"full": [0, 0.500], "tails": [None, [0.500, 0.90]]},
     ("b", 1, 1, 0): {"full": [0, 0.498], "tails": [None, [0.498, 0.95]]},
     ("c", 1, 1, 0): {"full": [0, 0.490], "tails": [None, [0.490, 0.99]]}}
print(H.suggested_plan(r, 1, 0.01, always_best=True)[0], H.suggested_plan(r, 1, 0.01, always_best=True, safe_margin=0.003)[0])
""")
    check("suggested_plan safe_margin: among plans within 0.3 points of the best full set, the safest (<= 1 missing)",
          code == 0 and out.strip() == "('a', 1, 1, 0) ('b', 1, 1, 0)", out)
    code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 Type 6"); M = h.M(23.1, True)
kw = dict(start_level=19, learned=sys.argv[1].split(","), wanted=H.COURSER_SET)
ps = [("at30", 1, 0, 0), ("coursier_v2", 20, 2, 0)]
r = F.Evaluator(h, M, max_budget=10, **kw).plans(ps, 20000, 5, at_most=True)
ok = True
for p in ps:
    py = H.simulate_plan(h, M, *p[:3], 10, runs=8000, seed=6, **kw)
    ok &= all(abs(r[p]["at_most"][B] - py["at_most"][B]) < 0.025 for B in range(11))
    ok &= all(r[p]["full"][B] is None or r[p]["full"][B] == r[p]["at_most"][B] for B in range(11))
print(ok, [round(100 * x, 1) for x in r[ps[1]]["at_most"][:5]])
""", T6L)
    check("horses_fast at_most[B] agrees with bdo.horses simulate_plan (within noise) and equals full[B] from the cap",
          code == 0 and out.startswith("True"), out)
else:
    print("skip horses_fast checks (numba not installed)")
code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H
print(H.effective_plan(("coursier_switch", 20, 2, 9), 15, 19), H.effective_plan(("coursier_switch", 1, 2, 16), 15, 19),
      H.effective_plan(("at30", 1, 0, 0), 15, 19), H.plan_name(("coursier_switch", 10, 4, 12), 5, 12, 0))
""")
check("effective_plan: a reached switch threshold is V2, a passed start level is the next level",
      code == 0 and out.strip() == "('coursier_v2', 20, 2, 0) ('coursier_switch', 20, 2, 16) ('at30', 1, 0, 0) "
      "from lvl 10, V2 until lvl 30, keep 1", out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--coupons-used")
check("horse_skills: --coupons-used without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--fewest-coupons")
check("horse_skills: --fewest-coupons without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--odds", "--lang", "fr")
check("horse_skills --odds --lang fr", code == 0 and "Ruade\t15.18" in out and "none\t10.7" in out, out)
code, out = run("horse_skills.py", D, "--training", "Expert 3")
check("horse_skills: bad Training level exits 2", code == 2 and "unknown Training level" in out, out)
code, out = run("horse_skills.py", "Pegasus", "--training", "Artisan 7")
check("horse_skills: unknown horse exits 2", code == 2 and "unknown horse" in out, out)

# --innate: a special horse = a known horse's weights without its extra innate skills, same 'no skill' weight
# (the T8 Type 11 reading in tests/data/sim_t8_types_2026-11-21.csv = Type 5 with Instant Accel innate)
code, out = run("horse_skills.py", "T8 Type 5", "--innate", "Accél. Fulgurante", "--training", "Artisan 7", "--check",
                "none=30.0751", "Ruade=7.6838", "Dérapage=4.1941", "Accélérer=5.6027", "Saut haut=3.8419")
check("horse_skills --innate: the T8 Type 11 reading = Type 5 with Instant Accel innate", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "T8 Type 6", "--innate", "S: Sideways", "--training", "Artisan 7", "--check",
                "none=17.1523", "Ruade=13.1")
check("horse_skills --innate: --check flags a special horse whose weights differ (special Type 4: Two-seater, other "
      "'no skill' weight)", code == 1 and "MISMATCH" in out, out)
code, out = run("horse_skills.py", "T8 Type 6", "--innate", "Sprint,S: Sideways", "--training", "Artisan 7", "--odds")
check("horse_skills --innate: header names the extra innate skills (an already innate one ignored), skill out of the draw",
      code == 0 and "# T8 Type 6 (an alias of T8 Type 4: the same data) + innate S: Sideways |" in out
      and "\nS: Sideways\t" not in out and "\nHind Kick\t" in out, out)
code, out = run("horse_skills.py", "T8 Type 5", "--innate", "Dark Sprint", "--training", "Artisan 7", "--odds")
check("horse_skills --innate: a skill the horse can't learn exits 2", code == 2 and "can't learn Dark Sprint" in out, out)

print("ALL OK" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
