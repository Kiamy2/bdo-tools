"""C39 summary table from c39_bench.jsonl."""
import json
rows = [json.loads(x) for x in open("c39_bench.jsonl")]
base = {(r["case"], r["C"], r["J"]): r["peak_MB"] for r in rows if r["variant"] == "none"}
print("case | coupons | values | variant | peak MB (minus simulation-only) | table time s (states / fill or sweep / query) | states")
for r in rows:
    if r["variant"] == "none":
        continue
    if r.get("failed"):
        print(f"{r['case']} | {r['C']} | {r['J'] + 1} | {r['variant']} | FAILED"); continue
    t = r["time"]; s = r["sizes"]
    parts = "/".join(str(t.get(k, "-")) for k in ("states", "csr", "fill", "sweep", "query") if k in t)
    st = s.get("states") or s.get("states_b1")
    print(f"{r['case']:<6} | {r['C']} | {r['J'] + 1} | {r['variant']:<3} | {r['peak_MB']:>5} ({r['peak_MB'] - base.get((r['case'], r['C'], r['J']), 0):>+5}) | {t['table_total']:>6} ({parts}) | {st}")
print("simulation-only peak MB:", base)
