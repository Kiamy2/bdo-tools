# bdo-tools

Small command-line tools for Black Desert Online, built to be used by Claude chats (compact output, no dependencies beyond Python 3).

## Get them

```
git clone --depth 1 https://github.com/Kiamy2/bdo-tools
cd bdo-tools
```

## Tools

| Tool | What it does | Example |
|---|---|---|
| `prices.py` | Central Market prices via [Arsha.io](https://api.arsha.io). Default rule: last sale if under 24 h old, else 7-day average, else base price (flagged). Options: `--tax`, `--latest`, `--avg N`, `--details`, `--sid`, `--region`, `--json`. | `python3 -I prices.py "Vell's Heart" 4998` |
| `items.py` | Item name ↔ ID lookup (no prices). | `python3 -I items.py --search "Advice of Valks"` |

Run any tool with `--help` for every option.

## Layout

```
bdo/net.py      HTTP + retries + network-block detection (shared)
bdo/items.py    item list download/cache (/tmp/bdo_tools) + name <-> ID lookup
bdo/market.py   Arsha market requests (batched) + the price rule
prices.py       CLI
items.py        CLI
tests/run_all.py  live regression tests for every tool
```

## Changing anything

Run `python3 -I tests/run_all.py` (it must print `ALL OK`) before every push, and keep `bdo/` backwards compatible: other tools import it.
