# Instructions for AI agents

**Using the tools:** read `README.md`, then the doc of the tool you need (`docs/prices.md`, `docs/items.md`). Run from the repo root with `python3 -I <tool>.py`. Pass all items in one call, use a long timeout (about 5 min), and don't print the cached item list.

**Changing the code:** follow `CONTRIBUTING.md`. Above all: `python3 -I tests/run_all.py` must print `ALL OK` before any push, keep `bdo/` backwards compatible, keep default output compact, and check licenses before porting code.

**Debugging data issues:** read `docs/data-sources.md` (API quirks, frequent temporary Arsha errors, other sources).
