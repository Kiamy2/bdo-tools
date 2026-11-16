# items.py: item name ↔ ID lookup

No prices; just names and IDs (e.g. to find an exact name for `prices.py`, or an ID for a wiki or database page).

```
python3 -I items.py "Vell's Heart" 4998          # resolve exact names and/or IDs
python3 -I items.py --search "Advice of Valks"    # every item whose name contains the text
python3 -I items.py --lang fr "Coeur de Vell"      # French names
python3 -I items.py --lang en,fr "Pierre noire"    # translate: English and French names side by side
```

- Names are matched case-insensitively. If nothing matches exactly, accents, `oe`/`œ`, typographic apostrophes and extra spaces are ignored, then all spaces and punctuation too (`Vells Heart`, `Lingot d'or 1000G`). A loose match is only accepted if it points to a single name; otherwise you get `NOT FOUND` with the candidates (e.g. `BD9 Armor N` vs `BD9+ Armor N`).
- If there's no match, similar names are suggested: names containing the text, then names containing every word in any order, then close spellings (typos).
- Some names are shared by several items (often untradeable event copies). All of them are listed, with a `SAME NAME` note.
- `--search` shows up to 50 results (`--limit N` to change that). It ignores case and accents too.
- `--lang` sets the names' language(s), comma-separated (default `en`). Names you give are matched in **any** of the listed languages, and the output has one name column per language (`name` for one language, `name_en`, `name_fr`... for several). Codes Arsha accepts: `en`, `de`, `fr`, `ru`, `es` (Spain), `sp` (Latin America), `pt`, `jp`, `kr`, `cn`, `tw`, `th`, `tr`, `id`. An unknown code stops with `UNKNOWN LANGUAGE` (exit code 2).
- Names are the official in-game names of each language. Some untranslated items keep their Korean name.
- The item list (about 71k items from Arsha.io, 4 MB per language) is cached in `/tmp/bdo_tools/` for 7 days (`--refresh-db` to re-download). Don't print it.

Output (UTF-8): tab-separated `id`, `name` (or one `name_<lang>` column per language), `note`. Exit codes: `0` OK · `2` some item NOT FOUND or UNKNOWN ID, or `UNKNOWN LANGUAGE` · `3` network blocked.
