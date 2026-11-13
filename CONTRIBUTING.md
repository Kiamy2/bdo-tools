# Contributing

These tools are mostly run by AI agents and read in chat, so **compact, reliable output** matters as much as correctness.

## Structure

- `bdo/`: the shared library. `net.py` handles HTTP and retries, `items.py` name ↔ ID, `market.py` Arsha and the price rule. Put logic here.
- `*.py` at the root: thin command-line tools on top of `bdo/`. Don't duplicate library logic in a tool.
- `docs/<tool>.md`: usage for each tool. `docs/data-sources.md`: APIs, quirks, research.
- `tests/run_all.py`: live regression tests for every tool.

## Rules

1. **Test before every push:** `python3 -I tests/run_all.py` must print `ALL OK`. Add a check for every new tool or option.
2. **Keep `bdo/` backwards compatible.** Tools import it. If an interface must change, update every caller in the same commit.
3. **Compact default output:** only what most users need, and extra data behind options (`--details`). Tab-separated tables, one row per item.
4. **Clear failure modes:** never fail silently or count unknown data as 0. Flag it in a `note` column and use non-zero exit codes.
5. **Never print large data** (the item list, raw API dumps) to stdout. Cache it to files.
6. **Be gentle with free APIs:** batch requests, cache, and retry with backoff.
7. **Standard library only,** unless a dependency clearly pays off. If you add one, pin its exact version.
8. **Licenses:** this repo is MIT. Only port code from projects under MIT-compatible permissive licenses (MIT, BSD, Apache-2.0, ISC...), and keep their copyright notice. **Never copy code from GPL/AGPL/LGPL projects (e.g. `bdomarket`) or from projects with no license**: re-implement from the maths or a description instead. Game mechanics and formulas are fine to re-implement.
9. **Docs and changelog:** update `docs/` and `CHANGELOG.md` in the same commit as any change to behaviour or options. Commit messages say what changed and why.

## Running

Python 3.8+. Run tools from the repo root, e.g. `python3 -I prices.py --help`. (The tools add their own directory to the import path, so they work with `-I`.)
