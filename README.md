# bdo-tools

Small command-line tools for **Black Desert Online**: live Central Market prices and item lookups. They're designed to be run by AI agents as well as humans: compact tab-separated output, clear warnings, no dependencies beyond Python 3.8+.

```
git clone --depth 1 https://github.com/Kiamy2/bdo-tools && cd bdo-tools
python3 -I prices.py "Vell's Heart" "Sharp Black Crystal Shard"
```

## Tools

| Tool | What it does | Docs |
|---|---|---|
| `prices.py` | Market prices via [Arsha.io](https://api.arsha.io): last sale if under 24 h old, else 7-day average, else base price. Optional after-tax column, averages, more details, any region. | [docs/prices.md](docs/prices.md) |
| `items.py` | Item name ↔ ID lookup and name search (no prices). | [docs/items.md](docs/items.md) |

Every tool supports `--help`.

## More

- [docs/data-sources.md](docs/data-sources.md): the APIs used, their quirks, other sources researched.
- [CONTRIBUTING.md](CONTRIBUTING.md): code structure, tests, rules for changes.
- [AGENTS.md](AGENTS.md): short instructions for AI agents.
- [CHANGELOG.md](CHANGELOG.md)

Data comes from Arsha.io, a free community API; please be gentle with it. Black Desert Online is a trademark of Pearl Abyss. This project isn't affiliated with Pearl Abyss or Arsha.io.
