# bdo-tools

Small command-line tools for **Black Desert Online**: live Central Market prices, item lookups, and a horse skill simulator. They're designed to be run by AI agents as well as humans: compact tab-separated output, clear warnings, no dependencies beyond Python 3.8+ (optional: numba makes `horse_skills.py --optimize` much faster, `pip install -r requirements-optional.txt`).

```
git clone --depth 1 https://github.com/Kiamy2/bdo-tools && cd bdo-tools
python3 -I prices.py "Vell's Heart" "Sharp Black Crystal Shard"
```

## Tools

| Tool | What it does | Docs |
|---|---|---|
| `prices.py` | Market prices via [Arsha.io](https://api.arsha.io): last sale if under 24 h old, else 7-day average, else base price. Optional after-tax column, averages, more details, any region. | [docs/prices.md](docs/prices.md) |
| `items.py` | Item name ↔ ID lookup, name search and translation between game languages (no prices). | [docs/items.md](docs/items.md) |
| `horse_skills.py` | Horse skill odds per level-up (as in the in-game growth simulator) and leveling-strategy simulation: gear, brand stone, coupons, Training level. Offline. | [docs/horse_skills.md](docs/horse_skills.md) |

Every tool supports `--help`.

## More

- [docs/horse-skills-report.md](docs/horse-skills-report.md): how horses learn skills, and which leveling strategy, gear or brand stone is worth it.
- [docs/data-sources.md](docs/data-sources.md): the APIs used, their quirks, other sources researched.
- [CONTRIBUTING.md](CONTRIBUTING.md): code structure, tests, rules for changes.
- [AGENTS.md](AGENTS.md): short instructions for AI agents.
- [docs/horse_skills_guide.md](docs/horse_skills_guide.md): for AI assistants guiding a player through a horse's leveling with `horse_skills.py`.
- [CHANGELOG.md](CHANGELOG.md)
- License: [MIT](LICENSE)

Market and item data come from Arsha.io, a free community API; please be gentle with it. Horse skill weights come from bdolytics.com (see the report). Black Desert Online is a trademark of Pearl Abyss. This project isn't affiliated with Pearl Abyss or Arsha.io.
