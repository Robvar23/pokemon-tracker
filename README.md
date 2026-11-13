# Pokémon Tracker

Watches Cardmarket card pages for you. When a new listing appears whose **seller comment** mentions one of
your keywords (and doesn't mention a word you ignore), it sends you a **Discord** message (and/or an email)
and can put the card straight into your Cardmarket cart.

It runs on your own computer, in its own Chrome window, with your own Cardmarket account.

## Start it

**Windows:** double-click `run.bat`. The first time it installs Python and sets itself up (about a minute).

**Mac:** install Python 3 from <https://www.python.org/downloads/> once. Then right-click `run-mac.command` ›
**Open** (only the first time; after that a double-click is enough).

The first start creates **`config.json`**. Open it in a text editor (Notepad / TextEdit), fill it in,
save, and start the tracker again. Already used the old version? Your `settings.txt` and `urls.txt` are
moved into `config.json` automatically.

A Chrome window opens and logs in to Cardmarket. If Cardmarket shows a captcha, log in by hand in that
window and press Enter in the tracker window. The login is remembered for next time.

## Discord alerts

1. In Discord: **Server Settings › Integrations › Webhooks › New Webhook**, pick your alerts channel,
   **Copy Webhook URL**.
2. Paste it in `config.json` at `"discord_webhook"`.
3. Send a test: double-click `test-notifications.bat` (Windows) or `test-notifications-mac.command` (Mac).

Keep the webhook link private: anyone who has it can post in that channel.

## config.json

See `config.example.json` for a filled-in example.

| Setting | What it does |
|---|---|
| `cardmarket` | Your Cardmarket username and password (optional: you can also log in by hand once). |
| `notify` | `discord` on/off + `discord_webhook`; `email` on/off + Gmail address, Gmail **App Password**, and where to send it. |
| `keywords.watch` | Alert only when the seller comment mentions one of these. Empty list = every new listing alerts you. |
| `keywords.ignore` | Never alert when the comment mentions one of these (wins over `watch`). |
| `criteria` | Only listings from these `countries`, in these `languages`, at least this `min_condition` (`MT`, `NM`, `EX`, `GD`, `LP`, `PL`, `PO`). Empty = anything. |
| `default_add_to_cart` | Put matches in your cart (for cards that don't say otherwise). Never buys anything. |
| `alert_existing_on_start` | `true` = also alert about listings that were already there when a card was added. |
| `load_more_presses` | How often to press "Show more results" on each card page. |
| `delays` | Random waits in seconds between pages and between rounds. Very short waits can get you blocked. |
| `cards` | The cards you watch, one block per card (see below). |

Each card:

```json
{
  "url": "https://www.cardmarket.com/en/Pokemon/Products/Singles/Prismatic-Evolutions/Umbreon-ex-V2-PRE161",
  "name": "Umbreon ex · 161 PRE",
  "languages": ["English"],
  "min_condition": "NM",
  "countries": [],
  "photos": "any",
  "add_to_cart": null,
  "use_all_keywords": true,  "keywords_off": [], "extra_keywords": [],
  "use_all_ignored": true,   "ignored_off": [],  "extra_ignored": []
}
```

Only `url` is required. New cards start on **English + Near Mint**. `photos` is `"any"`, `"yes"` (only
listings with seller photos) or `"no"`. `add_to_cart`: `true`, `false`, or `null` to follow
`default_add_to_cart`. Set `use_all_keywords` to `false` to switch off the words in `keywords_off` for
this card only; `extra_keywords` count for this card only. The same goes for the ignore list.

You can edit `config.json` while the tracker runs; it picks up changes at the start of the next round.

## Files it makes

- `config.json` – your settings (private: holds passwords and the webhook link)
- `state.json` – listings it has already seen, so a restart doesn't re-alert you, plus your match history
- `tracker.log` – everything it printed, with dates
- `chrome-profile/` – the tracker's own Chrome profile, so the Cardmarket login is remembered

None of these are uploaded to GitHub (see `.gitignore`).

## For developers

```
python -m pip install -r requirements.txt pytest
python -m pytest
```

`tracker/matching.py` holds all the "should this alert?" rules and has tests; `tracker/cardmarket.py`
reads the website; `tracker/notify.py` sends Discord and email; `tracker/runner.py` is the loop.
