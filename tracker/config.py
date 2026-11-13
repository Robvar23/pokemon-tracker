"""Reading and writing config.json (and migrating the old settings.txt + urls.txt)."""

import json
import os
import sys

# Personal files (config.json, state.json, tracker.log) live next to main.py, or next to the program once packaged.
APP_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False)
           else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
OLD_SETTINGS = os.path.join(APP_DIR, "settings.txt")
OLD_URLS = os.path.join(APP_DIR, "urls.txt")

DEFAULT_CONFIG = {
    "cardmarket": {"username": "", "password": ""},
    "notify": {
        "discord": True,
        "discord_webhook": "",
        "email": False,
        "email_from": "",
        "email_app_password": "",
        "email_to": "",
    },
    # Alerts tab: a listing only alerts you if its seller comment mentions one of these
    # (leave "watch" empty to be alerted about every new listing) ...
    "keywords": {
        "watch": ["No whitening", "Clean!", "Grade potential", "PSA 10 candidate",
                  "Perfect", "Mint", "Good centering", "Nice centering"],
        # ... and never if it mentions one of these.
        "ignore": ["damaged", "proxy", "OC", "Off center", "Offcenter", "Top heavy", "Bottom heavy",
                   "Left heavy", "Right heavy", "Tilted", "Skewed", "PSA 9", "PSA9", "PSA 8", "PSA8",
                   "Cert", "ACE 10", "GRAAD 9.5", "CGC 10", "CGC 10 Pristine"],
    },
    # Alerts tab "Only listings that fit" (empty = anything)
    "criteria": {"countries": [], "languages": [], "min_condition": ""},
    "default_add_to_cart": False,
    "alert_existing_on_start": False,
    "load_more_presses": 2,
    "delays": {"page_min": 22, "page_max": 47, "round_min": 57, "round_max": 123},
    "chrome_version": "",
    # One entry per watched card. Everything except "url" is optional.
    "cards": [],
}

CARD_DEFAULTS = {
    "url": "",
    "name": "",
    "languages": ["English"],
    "min_condition": "NM",
    "countries": [],
    "photos": "any",            # "any" | "yes" | "no"
    "add_to_cart": None,        # None = use default_add_to_cart
    "use_all_keywords": True,
    "keywords_off": [],
    "extra_keywords": [],
    "use_all_ignored": True,
    "ignored_off": [],
    "extra_ignored": [],
}


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def normalise_card(card):
    if isinstance(card, str):
        card = {"url": card}
    c = dict(CARD_DEFAULTS)
    c.update({k: v for k, v in card.items() if v is not None or k == "add_to_cart"})
    c["photos"] = c["photos"] if c["photos"] in ("any", "yes", "no") else "any"
    return c


def migrate_old_files():
    """Turn the old settings.txt + urls.txt into a config dict (or None if there are none)."""
    if not os.path.exists(OLD_SETTINGS):
        return None
    s = {}
    with open(OLD_SETTINGS, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                s[k.strip()] = v.strip()

    def placeholder(v):
        return not v or v.startswith(("your_", "you@"))

    def num(key, default):
        try:
            return int(s.get(key, default))
        except ValueError:
            return default

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = s.get("CARDMARKET_USERNAME") or s.get("CARDMARK_USERNAME", "")
    pw = s.get("CARDMARKET_PASSWORD") or s.get("CARDMARK_PASSWORD", "")
    cfg["cardmarket"] = {"username": "" if placeholder(user) else user, "password": "" if placeholder(pw) else pw}
    ef, ep, et = s.get("EMAIL_FROM", ""), s.get("EMAIL_APP_PASSWORD", ""), s.get("SEND_NOTIFS_TO", "")
    if not placeholder(ef) and ep and not placeholder(et):
        cfg["notify"].update(email=True, email_from=ef, email_app_password=ep, email_to=et)
    cfg["default_add_to_cart"] = s.get("AUTO_ADD_TO_CART", "").lower() in ("1", "true", "yes", "y", "on")
    cfg["chrome_version"] = s.get("CHROME_VERSION", "")
    cfg["delays"] = {
        "page_min": num("DELAY_BETWEEN_PAGES_MIN", 22), "page_max": num("DELAY_BETWEEN_PAGES_MAX", 47),
        "round_min": num("DELAY_BETWEEN_PASSES_MIN", 57), "round_max": num("DELAY_BETWEEN_PASSES_MAX", 123),
    }
    if os.path.exists(OLD_URLS):
        with open(OLD_URLS, encoding="utf-8") as f:
            urls = [u.strip() for u in f if u.strip().startswith("http") and not u.strip().endswith("/...")]
        cfg["cards"] = [{"url": u} for u in urls]
    return cfg


def load_config():
    """Returns (config, note). Creates config.json from old files or defaults if needed."""
    note = ""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = migrate_old_files()
        if raw is not None:
            note = "Moved your settings from settings.txt and urls.txt into config.json."
        else:
            raw = json.loads(json.dumps(DEFAULT_CONFIG))
            note = "Created config.json. Open it, fill in your details, and start the tracker again."
        save_config(raw)
    cfg = _merge(DEFAULT_CONFIG, raw)
    cfg["keywords"] = _merge(DEFAULT_CONFIG["keywords"], raw.get("keywords", {}))
    cfg["cards"] = [normalise_card(c) for c in raw.get("cards", []) if c]
    return cfg, note


def save_config(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_FILE)
