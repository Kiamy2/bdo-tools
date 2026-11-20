"""K2: time and peak memory of horse_skills.py --optimize, reset-aware sweep (this tree) against the no-reset
P32 sweep (commit e7de4a0, checked out in OLD). Each run in its own process; peak RSS from getrusage.
Run from the repo root: python3 -I wip/horse-skills/proto/k2_bench.py OLD"""
import os, subprocess, sys, time

OLD = sys.argv[1]
T8 = "T8 example (bdolytics icon horse_71)"
cases = [(T8, "Skilled 1", "20", ()), (T8, "Skilled 1", "40", ()), ("Mythical Diné", "Artisan 7", "20", ()),
         (T8, "Skilled 1", "40", ("--low-memory",)), (T8, "Skilled 1", "20", ("--selection-coupon", "planned"))]
for horse, tr, B, extra in cases:
    for label, root in (("new", "."), ("old", OLD)):
        r = subprocess.Popen([sys.executable, "-I", "horse_skills.py", horse, "--training", tr, "--optimize", B,
                              *extra], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        t = time.time()
        out = r.stdout.read()
        _, status, ru = os.wait4(r.pid, 0)
        r.returncode = os.waitstatus_to_exitcode(status)
        dt = time.time() - t
        rss = ru.ru_maxrss / 1024
        best = next((l for l in out.splitlines() if l.startswith(B + "\t")), "?")
        print(f"{label} {horse[:13]:13s} {tr:9s} {B:>2s} {' '.join(extra):28s} {dt:6.1f} s  peak {rss:6.0f} MB"
              f"  rc {r.returncode}  | {best[:60]}", flush=True)
