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
    first = lambda r, i: float(r[i].split("/")[0].strip("%<>"))
    ok = first(rows["ideal"], 2) >= first(rows["coursier"], 2) >= first(rows["natural"], 2)
check("horse_skills simulation table", ok, out)
code, out = run("-c", "import sys; sys.path.insert(0, '.'); from bdo import horses as H; c = H.COURSER_SET; "
                "print(H.rule_plan(1), H.rule_plan(6), H.rule_plan(6, wanted=c), H.rule_plan(2, wanted=c), "
                "H.rule_plan(9), H.rule_plan(15), H.rule_plan(24), H.rule_plan(25), H.rule_plan(30, wanted=c), "
                "H.rule_plan(20, start_level=15))")
check("rule_plan: the compact rules (1 / 2-24 S2 / 25+ switch; courser starts 2-6), halves rounded up, partway horse",
      code == 0 and out.strip() == "('at30', 1, 0, 0) ('coursier_v2', 21, 5, 0) ('coursier_v2', 18, 5, 0) "
      "('coursier_v2', 26, 1, 0) ('coursier_v2', 15, 8, 0) ('coursier_v2', 10, 14, 0) ('coursier_v2', 10, 23, 0) "
      "('coursier_switch', 10, 24, 12) ('coursier_switch', 10, 24, 12) ('coursier_v2', 16, 19, 0)", out)
code, out = run("-c", "import sys; sys.path.insert(0, '.'); from bdo import horses as H; "
                "h = H.get_horse(H.load_data(), 'T8 example (bdolytics icon horse_71)'); "
                "d = H.get_horse(H.load_data(), 'Mythical Diné'); "
                "print(H.CLASSIC_FODDER, H._cycle_skill(H.CLASSIC_FODDER, h.weights), "
                "H._cycle_skill(H.CLASSIC_FODDER, d.weights))")
check("S1 swaps Fore Chop first; S2 cycles the heavier fodder, Hind Kick on ties (T8)", code == 0 and out.strip() ==
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
          and re.search(r"^20\t[\d.]+%\tfrom lvl \d+(-\d+)?, S1 until", out, re.M), out)
    lv = {int(l.split("\t")[0]): [float(x) for x in l.split("\t")[1:]] for l in out.split("# Average learned")[-1].splitlines()
          if re.match(r"^\d+\t[\d.]+", l)}
    check("horse_skills --optimize: average learned skills per level (levels 1-30, rising, ~13-16 at 30 on the T8 Skilled 1)",
          sorted(lv) == list(range(1, 31)) and all(lv[L][0] <= lv[L + 1][0] for L in range(1, 30))
          and all(12 <= x <= 16 for x in lv[30]), out[-1500:])
    sug = re.search(r"^20\t(from lvl \d+, S[12] until [^\t]+, keep \d+)\t([\d.]+)%\t([\d.]+)%\t"
                    r"([\d.]+)%\t(\d\+?)\t[\d.]+\t[\d.]+\t(rule \(best ([\d.]+)%\)|best)", out, re.M)
    check("horse_skills --optimize: suggested plan per budget (20 coupons, rechecked with fresh horses: within 1 point "
          "of the best, and below the search's lucky best + 0.5; full set <= missing 1 <= missing 2)",
          sug is not None and (sug.group(7) is None or float(sug.group(2)) >= float(sug.group(7)) - 1.0)
          and float(sug.group(2)) <= float(m.get("20", 0)) + 0.5
          and float(sug.group(2)) <= float(sug.group(3)) <= float(sug.group(4)), out)
    fr = [l.split("\t") for l in out.split("# Plans compared on three criteria")[-1].split("# Average learned")[0].splitlines()
          if re.match(r"^(from|no swaps)", l)]
    a30 = [x for x in fr if x[0].startswith("no swaps")]
    check("horse_skills --optimize: three-criteria comparison by default (hard case: 2+ plans, stuck horses shown, "
          "a pick per criterion; with --when-stuck stop, at30 listed as the cheapest, about 16% stuck)",
          "# Plans compared on three criteria, with up to 20 coupons" in out and len(fr) >= 2
          and all(re.match(r"^[\d.]+%\*?$", x[2]) for x in fr) and {"chance", "coupons", "safe"} <= set(",".join(x[-1] for x in fr).split(","))
          and "unless its name ends with '| not stuck' or '| successes'" in out and "# when stuck (fewer learned" in out
          and len(a30) == 1 and re.match(r"^1[4-8]\.\d%$", a30[0][2]) and "coupons" in a30[0][-1], out)
    sugrow = lambda o, B: next((l.split("\t") for l in o.splitlines() if l.startswith(f"{B}\tfrom lvl")), None)
    pct = lambda x: float(x.strip("%*<>"))         # "<0.02%" / ">99.98%": the bound
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
    check("horse_skills --optimize --engine numba (S2 best at 10 coupons, about 62%)",
          code == 0 and "fast engine" in out and 55 <= float(m.get("10", 0)) <= 70
          and re.search(r"^10\t[\d.]+%\tS2: from lvl", out, re.M), out)
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
          re.search(r"^plan for 2 coupons\t[\d.]+\t\d+\t\d+\t\d+\t[<>]?[\d.]+%$", out, re.M)
          and all(abs(float(sug[B][6]) / float(sug[B][7]) - pct(sug[B][2]) / 100) < 0.01 for B in sug), out)
    check("horse_skills: effective plan (a switch threshold already reached prints as S2), alias as typed, in-game "
          "count, French names in learned:, sure-hit note, innate skill in --learned ignored with a note",
          "S1 until 9 learned" not in out and "T8 Type 6 (an alias of T8 Type 4" in out
          and "learned: 15 + 1 innate (Sprint) = 16 in game: Ruade, Cabrade" in out
          and "every skill left to learn is wanted (" in out and "ignoring 'Sprint' in --learned: innate" in out, out)
    code, out = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--gear", "--level", "19", "--learned",
                    T6L, "--optimize", "5")
    fw = [l.split("\t") for l in out.split("# Plans compared on three criteria")[-1].split("# Average learned")[0].splitlines()
          if re.match(r"^(from|no swaps)", l)]
    check("horse_skills --optimize: one plan best on every criterion (live test 1: S2 from lvl 20), stuck 0% (15 learned "
          ">= 6 wanted: impossible), at30 beaten; 2-coupon suggestion rechecked: from lvl 24 (the 4,000-horse pick was 25)",
          code == 0 and "# One plan is the best on every criterion." in out and len(fw) == 1
          and fw[0][0] == "from lvl 20, S2 until lvl 30, spend <= 2 while leveling [s2:L20:C2]" and fw[0][2] == "0%"
          and fw[0][-1] == "chance,coupons,safe" and "# at30 (no swaps" in out
          and re.search(r"^2\tfrom lvl 24, S1 until lvl 30, keep 1\t", out, re.M), out)
    code4, out4 = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--gear", "--level", "19", "--learned",
                      T6L, "--optimize", "5", "--plan", "s2:L23:C1", "--plan", "at30", "--coupons-used", "3")
    check("horse_skills --plan: your plans listed in the comparison (marked, with their code) and in --coupons-used",
          code4 == 0 and "from lvl 23, S2 until lvl 30, spend <= 1 while leveling [s2:L23:C1] (yours)\t" in out4
          and "[at30] (yours)\t" in out4 and "\tyour plan s2:L23:C1\tyour plan at30" in out4
          and "# at30 (no swaps" not in out4, out4)
    code5, out5 = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--level", "19", "--learned", T6L,
                      "--optimize", "5", "--boosts", "none,gear,both")
    rows5 = [l.split("\t") for l in out5.split("coupons\tsuggested plan\tfor")[-1].split("# Compared")[0].splitlines()
             if re.match(r"^\d+\t", l)]
    check("horse_skills --boosts none,gear,both: one plan per budget for the 3 boosts (live test 1: 2 coupons from lvl 23, "
          "item 2), values a/b/c rising with the boosts, the comparison per boost (explained once)",
          code5 == 0 and len(rows5) == 5 and all(x[2] == "a,b,c" for x in rows5)
          and rows5[1][1] == "from lvl 23, S1 until lvl 30, keep 1"
          and all(pct(x[3].split("/")[0]) <= pct(x[3].split("/")[1]) <= pct(x[3].split("/")[2]) for x in rows5)
          and out5.count("# Compared on three criteria, ") == 3 and out5.count("# Plans compared on three criteria") == 1, out5)
    code7, out7 = run("-c", """
import sys; sys.path.insert(0, ".")
import numpy as np
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)"); M = h.M(H.training_bonus("Skilled 1"))
ev = F.Evaluator(h, M, max_budget=20, wanted=H.TRAVEL_SET, tickets=4)
w, n, W, MM = ev.args; lmask, wmask, fod, cyc, order, rare = ev.masks
args = (2000, 7, w, n, W, MM, 6, 10, 19, 4, 1, lmask, wmask, fod, cyc, order, rare, ev.pb, 0, 10, 0, False, True, 30)
a, b = F._many30(*args), F._many30_t(*args)
st = ev.states_at(("coursier_v2", 10, 19, 0), 10, 2000, 7)
c = np.array([len(x[0]) for x in st]); t = np.array([x[3] for x in st]); low = c <= np.percentile(c, 10)
print(all((x == y).all() for x, y in zip(a, b[:3])), list(b[3]) == list(t), 0 <= t.min() <= t.max() <= 4,
      t[low].mean() <= t[~low].mean(), t.mean() > 0)
""")
    code8, out8 = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)"); M = h.M(H.training_bonus("Skilled 1"))
p = ("coursier_v2", 10, 19, 0)
ok = True
base = F.Evaluator(h, M, max_budget=20, wanted=H.TRAVEL_SET, tickets=5).plans([p], 20000, 3)[p]
for pol in (dict(), dict(ticket_from=15), dict(ticket_behind=0.0), dict(ticket_behind=1.0, ticket_ref="always")):
    ev = F.Evaluator(h, M, max_budget=20, wanted=H.TRAVEL_SET, tickets=5, **pol)
    r = ev.plans([p], 20000, 3)[p]
    c = ev.ticket_curve(p)
    py = H.simulate_plan(h, M, *p[:3], 20, runs=4000, seed=4, wanted=H.TRAVEL_SET, tickets=5,
                         ticket_from=pol.get("ticket_from", 0), ticket_curve=None if c is None else list(c))
    ok &= abs(r["full"][20] - py["full"][20]) < 0.03 and abs(r["tickets_used"] - py["tickets_used"]) < 0.1
    ok &= 0 <= r["tickets_used"] <= 5 and (r["tickets_used"] < 4.9) == ("ticket_behind" in pol)
ok &= base["full"] == F.Evaluator(h, M, max_budget=20, wanted=H.TRAVEL_SET, tickets=5, ticket_from=0).plans([p], 20000, 3)[p]["full"]
print(ok)
""")
    check("ticket policies (from level L; only while behind the plan's average minus d, the average without tickets or "
          "with them): fast vs Python within noise, tickets_used, the default unchanged", code8 == 0 and out8.strip() == "True", out8)
    check("_many30 (3 values, kept for older scripts) = _many30_t's first 3; states_at has the tickets left (0-4, the "
          "unlucky horses no more than the others)", code7 == 0 and out7.split() == ["True"] * 5, out7)
    code6, out6 = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Skilled 1", "--wanted",
                      "travel", "--optimize", "6", "--no-frontier", "--replan-check", "26", "--tickets", "2")
    rows6 = [l.split("\t") for l in out6.split("re-planned plan\n")[-1].splitlines() if re.match(r"^\d+\t\d+\t\d+\t\d\t", l)]
    gain6 = re.search(r"# average gain: ([+-][\d.]+) points", out6)
    check("horse_skills --replan-check 26 --tickets 2: 30 unlucky horses (fewest learned skills at 26) with their "
          "tickets left, kept vs re-planned on the same fresh horses, average gain printed",
          code6 == 0 and "\tcoupons left\ttickets left\t" in out6 and len(rows6) == 30
          and all(0 <= int(x[3]) <= 2 for x in rows6) and gain6 is not None and -5 < float(gain6.group(1)) < 10
          and all(int(x[0]) <= int(rows6[-1][0]) for x in rows6), out6[-2500:])
    code2, out2 = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--gear", "--level", "19", "--learned",
                      T6L, "--optimize", "5", "--no-frontier")
    code3, out3 = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--level", "19", "--learned", T6L,
                      "--optimize", "3", "--prefer", "coupons", "--frontier-tol", "0,0,0", "--frontier-rows", "2")
    fw3 = [l.split("\t") for l in out3.split("# Plans compared on three criteria")[-1].split("# Average learned")[0].splitlines()
           if re.match(r"^(from|no swaps)", l)]
    check("horse_skills --no-frontier, --prefer coupons (sorted by coupons), --frontier-tol 0,0,0, --frontier-rows 2",
          code2 == 0 and "Plans compared" not in out2 and code3 == 0 and "sorted by coupons" in out3
          and 1 <= len(fw3) <= 3 and [float(x[4].rstrip("*")) for x in fw3] == sorted(float(x[4].rstrip("*")) for x in fw3)
          and ("more plan(s) on the frontier not shown" in out3 or len(fw3) <= 2), out2[-300:] + out3)
    code, out = run("horse_skills.py", "T8 Type 5", "--innate", "Instant Accel", "--training", "Artisan 7", "--level", "25",
                    "--learned", "Hind Kick,Fore Chop,Drift,High Jump,Quick Stop,Charge,Roar", "--optimize", "3")
    src = [l.split("\t")[-1] for l in out.splitlines() if re.match(r"^[1-3]\t(from|no swaps)", l)]
    check("R2: with --innate the general rule isn't used (the best plan is suggested, with a note)",
          code == 0 and "isn't used here (--innate)" in out and src == ["best"] * 3, out)
    code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)"); M = h.M(H.training_bonus("Skilled 1"))
ps = [("at30", 1, 0, 0), ("coursier_switch", 12, 12, 11)]
ev = F.Evaluator(h, M, max_budget=20, wanted=H.TRAVEL_SET)
a = ev.plans(ps, 20000, 3, used=True, stuck=True)
b = ev.plans(ps, 20000, 3, used=True)
c = ev.plans(ps, 20000, 3, used=True, stuck=True, coupon="fallback")
ok = True
for p in ps:
    py = H.simulate_plan(h, M, *p[:3], 20, runs=4000, seed=4, switch_at=p[3], wanted=H.TRAVEL_SET)
    ok &= a[p]["full"] == b[p]["full"] and all(abs(x - y) < 1e-6 for x, y in zip(a[p]["used"][12:], b[p]["used"][12:]))
    ok &= a[p]["stuck"] == c[p]["stuck"] and abs(a[p]["stuck"] - py["stuck"]) < 0.025
    ok &= abs(a[p]["used_ok"][20] - py["used_ok"][20]) < 0.4 and 0 < a[p]["stuck"] < 0.3
print(ok, [round(a[p]["stuck"], 3) for p in ps], [round(a[p]["used_ok"][20], 2) for p in ps])
""")
    code2, out2 = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H, horses_fast as F
h = H.get_horse(H.load_data(), "T8 example (bdolytics icon horse_71)"); M = h.M(H.training_bonus("Skilled 1"))
ps = [("at30", 1, 0, 0), ("coursier_switch", 10, 14, 12), ("coursier", 5, 20, 0)]
r = {m: F.Evaluator(h, M, max_budget=20, wanted=H.TRAVEL_SET, when_stuck=m).plans(ps, 20000, 3, used=True, tails=True,
     stuck=True) for m in ("stop", "continue")}
ok = all(r["stop"][p]["full"] == r["continue"][p]["full"] and r["stop"][p]["stuck"] == r["continue"][p]["stuck"]
         and r["stop"][p]["used_ok"] == r["continue"][p]["used_ok"]
         and r["stop"][p]["used"][20] < r["continue"][p]["used"][20] - 0.3
         and r["stop"][p]["tails"][20][1] < r["continue"][p]["tails"][20][1] for p in ps)
st = r["stop"][ps[0]]
ok &= abs(st["used"][20] - (1 - st["stuck"]) * st["used_ok"][20]) < 1e-6        # at30: stuck horses spend 0
for p in ps:
    py = H.simulate_plan(h, M, *p[:3], 20, runs=4000, seed=8, switch_at=p[3], wanted=H.TRAVEL_SET, when_stuck="stop")
    ok &= abs(py["used"][20] - r["stop"][p]["used"][20]) < 0.45 and abs(py["full"][20] - r["stop"][p]["full"][20]) < 0.035
kw = dict(wanted=H.TRAVEL_SET, start_level=25, learned=["Hind Kick", "Fore Chop", "Drift"])   # certainly stuck at 25
q = ("coursier", 26, 10, 0)
u = [F.Evaluator(h, M, max_budget=10, when_stuck=m, **kw).plans([q], 2000, 1, used=True)[q]["used"][10] for m in ("stop", "continue")]
v = [H.simulate_plan(h, M, "coursier", 26, 10, 10, runs=1000, seed=1, when_stuck=m, **kw)["used"][10] for m in ("stop", "continue")]
ok &= u[0] == 0 and v[0] == 0 and u[1] > 3 and v[1] > 3
print(ok, u, v)
""")
    check("--when-stuck stop: same full set, stuck share and non-stuck average as continue; fewer coupons; at30's stuck "
          "horses spend 0; a horse certainly stuck while leveling stops swapping (both engines); Python vs fast within noise",
          code2 == 0 and out2.startswith("True"), out2)
    check("horses_fast stuck share and used_ok (horses not stuck): split doesn't change full / used, agrees with "
          "bdo.horses simulate_plan within noise, same stuck share with a Selection Coupon", code == 0 and out.startswith("True"), out)
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
check("effective_plan: a reached switch threshold is S2, a passed start level is the next level",
      code == 0 and out.strip() == "('coursier_v2', 20, 2, 0) ('coursier_switch', 20, 2, 16) ('at30', 1, 0, 0) "
      "from lvl 10, S2 until lvl 30, keep 1", out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--coupons-used")
check("horse_skills: --coupons-used without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--coupons", "10", "--strategy", "at30", "--runs", "200",
                "--when-stuck", "continue")
check("horse_skills --when-stuck continue: stated in the header", code == 0 and "# when stuck (fewer learned skills than "
      "wanted ones: the full set can't be reached any more): continue" in out, out)
code, out = run("horse_skills.py", "T8 Type 6", "--training", "Artisan 9", "--level", "29", "--learned", "Hind Kick,Fore Chop,"
                "Drift,Start Accel,High Jump,Quick Stop,Charge,Quick Back,Streak Leap,Roar,Caution,Quick Ride,S: Hind Kick,"
                "S: Fore Chop,S: Sideways,Instant Accel,Sideways", "--optimize", "3", "--coupons-used", "0,1", "--no-frontier")
check("horse_skills --coupons-used 0 (no swaps), and no '100.0%' for chances that aren't certain (>99.98% / >99.9%)",
      code == 0 and "# plan for 0-1 coupons: no swaps while leveling" in out and "100.0%" not in out
      and re.search(r"\t>99\.9[0-9]*%", out), out)
code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H
ok = [H.parse_plan(t) for t in ("s2:L20:C2", "S1-S2:c24:L10:T12", "at30", "s1:L5:C3")]
bad = 0
for t in ("s2:L20", "s2:L20:C2:T5", "v2:L20:C2", "s1:L20:X2", "at30:C2", "s1:L0:C2"):
    try:
        H.parse_plan(t)
    except H.DataError:
        bad += 1
print(ok, [H.plan_code(p) for p in ok], bad)
""")
check("parse_plan / plan_code: s1, s2, s1-s2 (L, C, T in any order, any case), at30; 6 bad plans refused",
      code == 0 and out.strip() == "[('coursier_v2', 20, 2, 0), ('coursier_switch', 10, 24, 12), ('at30', 1, 0, 0), "
      "('coursier', 5, 3, 0)] ['s2:L20:C2', 's1-s2:L10:C24:T12', 'at30', 's1:L5:C3'] 6", out)
for args, what in ((["--optimize", "3", "--replan-check", "30"], "--replan-check 30"),
                   (["--replan-check", "20"], "--replan-check without --optimize")):
    code, out = run("horse_skills.py", D, "--training", "Artisan 7", *args)
    check(f"horse_skills {what} exits 2", code == 2, out)
for args, what in ((["--optimize", "3", "--boosts", "none,gear", "--gear"], "with --gear"),
                   (["--optimize", "3", "--boosts", "none,wings"], "an unknown boost"), (["--boosts", "none,gear"], "without --optimize")):
    code, out = run("horse_skills.py", D, "--training", "Artisan 7", *args)
    check(f"horse_skills --boosts {what} exits 2", code == 2, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--plan", "s2:L20:C2")
check("horse_skills: --plan without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--prefer", "safe")
check("horse_skills: --prefer without --optimize exits 2", code == 2 and "--optimize" in out, out)
code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H
rp = H.rule_plan(5)
other = ("at30", 1, 0, 0)
mk = lambda f, u: {"full": [None] * 5 + [f], "used": [None] * 5 + [u], "tails": [None] * 5 + [[f, 0.9]]}
r = {rp: mk(0.500, 4.0), other: mk(0.505, 3.5)}
r2 = {rp: mk(0.500, 4.0), other: mk(0.505, 3.9)}
print(H.suggested_plan(r, 5, 0.01, cheaper=0.2)[1], H.suggested_plan(r2, 5, 0.01, cheaper=0.2)[1],
      H.suggested_plan(r, 5, 0.01)[1])
""")
check("R1: the rule's plan isn't suggested when a plan at least as good uses 0.2+ fewer coupons",
      code == 0 and out.split() == ["cheaper", "rule", "rule"], out)
code, out = run("-c", """
import sys; sys.path.insert(0, ".")
from bdo import horses as H
mk = lambda f, t, u: {"full": [None, f], "used": [None, u], "tails": [None, [f, t]]}
r = {("a", 1, 1, 0): mk(0.9876, 0.999, 2.34), ("b", 1, 1, 0): mk(0.9875, 0.999, 0.80), ("c", 1, 1, 0): mk(0.9874, 0.990, 0.5)}
print(H.suggested_plan(r, 1, 0.01, always_best=True, safe_margin=0.003)[0])
""")
check("suggested_plan: among plans tied on the full set and on <= 1 missing, the one using the fewest coupons",
      code == 0 and out.strip() == "('b', 1, 1, 0)", out)
code, out = run("horse_skills.py", "T8 Type 2", "--training", "Artisan 7", "--level", "2", "--learned",
                "Ruade,Cabrade,Charge", "--odds")
check("horse_skills: more learned skills than level - 1 -> warning (special horse or typo)",
      code == 0 and "3 learned skills at level 2" in out and "--innate" in out, out)
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    src = open(os.path.join(ROOT, "tests", "data", "sim_t8_choky_artisan8.csv"), encoding="utf-8").read()
    hf = os.path.join(tmp, "t8.csv")
    with open(hf, "w", encoding="utf-8") as f:
        f.write(src.replace("# learned:", "# tier: T8\n# type: 1\n# innate: Sprint\n# learned:"))
    code, out = run("horse_skills.py", "--horse-file", hf, "--training", "Artisan 8", "--odds")
check("horse_skills --horse-file headers: tier (default target set courser), type (shown), innate (out of the draw)",
      code == 0 and "(in-game type 1)" in out and "# wanted: courser set" in out and "\nSprint\t" not in out
      and "\nHind Kick\t" in out, out)
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
