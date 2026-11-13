# bdo-tools: rules for Claude

- Shared code lives in `bdo/`; tools (`prices.py`, `items.py`, ...) are thin CLIs on top. Don't duplicate logic in a tool; put it in `bdo/`.
- Before every push: `python3 -I tests/run_all.py` must print `ALL OK`. When you add a tool or option, add a check for it.
- Keep `bdo/` backwards compatible, since other tools import it. If an interface must change, update every caller in the same commit.
- Keep default output compact (it's read by chats, and every column costs tokens). Extra data goes behind options.
- Never print large data (the item list, raw API dumps) into the conversation.
- Each commit message says what changed and why. The usage docs live in the user's claude.ai project ("Black Desert", `tools/bdo-prices.md`). If behaviour or options change, tell the user so those docs get updated.
