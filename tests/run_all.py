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
code, out = run("-c", "import sys; sys.path.insert(0, '.'); from bdo import horses as H; "
                "print(H.rule_plan(20), H.rule_plan(9), H.rule_plan(27), H.rule_plan(20, start_level=15))")
check("rule_plan: fitted, formula, nearest fitted below, partway horse", code == 0 and out.strip() ==
      "('coursier_switch', 10, 15, 11) ('coursier_v2', 16, 9, 0) ('coursier_switch', 9, 22, 14) "
      "('coursier_switch', 16, 15, 11)", out)
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
    code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Skilled 1", "--optimize", "20")
    m = dict(re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M))
    check("horse_skills --optimize: coursier_switch best at 20 coupons on a hard case (T8 Skilled 1, about 71%)",
          code == 0 and 66 <= float(m.get("20", 0)) <= 76
          and re.search(r"^20\t[\d.]+%\tcoursier_switch: from lvl \d+(-\d+)?, V0 until", out, re.M), out)
    sug = re.search(r"^20\t(from lvl \d+, V0 until \d+ learned skills, then V2, keep \d+)\t([\d.]+)%\t([\d.]+)%\t"
                    r"([\d.]+)%\t(\d)\t(rule|best)", out, re.M)
    check("horse_skills --optimize: suggested plan per budget (20 coupons: one switch plan, within 1 point of the best; "
          "full set <= missing 1 <= missing 2)", sug is not None and float(sug.group(2)) >= float(m.get("20", 0)) - 1.0
          and float(sug.group(2)) <= float(sug.group(3)) <= float(sug.group(4)), out)
    code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--optimize", "10", "--engine", "numba")
    m = dict(re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M))
    code2, out2 = run("horse_skills.py", D, "--training", "Artisan 7", "--optimize", "10", "--engine", "numba", "--low-memory")
    m2 = dict(re.findall(r"^(\d+)\t([\d.]+)%\t", out2, re.M))
    check("horse_skills --optimize --low-memory: same best chances (16-bit values)", code2 == 0 and len(m2) == 11
          and all(abs(float(m2[b]) - float(m.get(b, -9))) <= 0.11 for b in m2), out2)
    check("horse_skills --optimize --engine numba (coursier_v2 best at 10 coupons, about 62%)",
          code == 0 and "fast engine" in out and 55 <= float(m.get("10", 0)) <= 70
          and re.search(r"^10\t[\d.]+%\tcoursier_v2", out, re.M), out)
else:
    print("skip horses_fast checks (numba not installed)")
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--odds", "--lang", "fr")
check("horse_skills --odds --lang fr", code == 0 and "Ruade\t15.18" in out and "none\t10.7" in out, out)
code, out = run("horse_skills.py", D, "--training", "Expert 3")
check("horse_skills: bad Training level exits 2", code == 2 and "unknown Training level" in out, out)
code, out = run("horse_skills.py", "Pegasus", "--training", "Artisan 7")
check("horse_skills: unknown horse exits 2", code == 2 and "unknown horse" in out, out)

print("ALL OK" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
