"""Deciding whether a listing should alert you. Pure logic, no browser, so it can be tested."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CONDITIONS = ["MT", "NM", "EX", "GD", "LP", "PL", "PO"]          # best to worst
COND_NAMES = {"MT": "Mint", "NM": "Near Mint", "EX": "Excellent", "GD": "Good",
              "LP": "Light Played", "PL": "Played", "PO": "Poor"}
NAME_TO_COND = {v.lower(): k for k, v in COND_NAMES.items()}
NAME_TO_COND.update({"lightly played": "LP", "light-played": "LP", "slightly played": "EX",
                     "good (gd)": "GD"})

# Cardmarket's own ids for the product-page filters (?language=1&minCondition=2)
LANG_ID = {"English": 1, "French": 2, "German": 3, "Spanish": 4, "Italian": 5, "S-Chinese": 6,
           "Japanese": 7, "Portuguese": 8, "Russian": 9, "Korean": 10, "T-Chinese": 11,
           "Dutch": 12, "Polish": 13}
LANGUAGE_ALIASES = {"simplified chinese": "S-Chinese", "chinese (simplified)": "S-Chinese",
                    "traditional chinese": "T-Chinese", "chinese (traditional)": "T-Chinese"}
COND_ID = {"MT": 1, "NM": 2, "EX": 3, "GD": 4, "LP": 5, "PL": 6}


def condition_code(text):
    """'Near Mint' / 'NM' / 'nm' -> 'NM'; unknown -> ''."""
    t = (text or "").strip()
    if t.upper() in CONDITIONS:
        return t.upper()
    return NAME_TO_COND.get(t.lower(), "")


def language_name(text):
    t = (text or "").strip()
    for name in LANG_ID:
        if t.lower() == name.lower():
            return name
    return LANGUAGE_ALIASES.get(t.lower(), "")


def word_regex(word):
    """Whole-word, case-insensitive: 'PSA 10 candidate' doesn't match 'PSA 100 candidate'.
    'Mint' on its own never matches the 'Mint' in 'Near Mint' / 'near-mint'."""
    parts = [re.escape(p) for p in word.strip().split()]
    not_near = r"(?<!near\s)(?<!near-)" if word.strip().lower() == "mint" else ""
    return re.compile(r"(?<!\w)" + not_near + r"\s+".join(parts) + r"(?!\w)", re.IGNORECASE)


def found_words(text, words):
    text = text or ""
    return [w for w in words if w.strip() and word_regex(w).search(text)]


def _merge_words(base, off, extra):
    off_l = {w.lower() for w in off}
    out = [w for w in base if w.lower() not in off_l]
    for e in extra:
        if e.strip() and e.lower() not in {w.lower() for w in out}:
            out.append(e)
    return out


def words_for_card(cfg, card):
    """Your Alerts keywords for this card: the global lists, minus the ones switched off, plus extras."""
    kw = cfg["keywords"]
    watch = _merge_words(kw["watch"], [] if card.get("use_all_keywords", True) else card.get("keywords_off", []),
                         card.get("extra_keywords", []))
    ignore = _merge_words(kw["ignore"], [] if card.get("use_all_ignored", True) else card.get("ignored_off", []),
                          card.get("extra_ignored", []))
    return watch, ignore


def fits(listing, languages=(), min_condition="", countries=(), photos="any"):
    """True if the listing passes these filters. Unknown values (couldn't read them) are let through."""
    lang = listing.get("language", "")
    if languages and lang and lang.lower() not in {l.lower() for l in languages}:
        return False
    cond = listing.get("condition", "")
    if min_condition and cond in CONDITIONS and min_condition in CONDITIONS:
        if CONDITIONS.index(cond) > CONDITIONS.index(min_condition):
            return False
    country = listing.get("country", "")
    if countries and country and country.lower() not in {c.lower() for c in countries}:
        return False
    has_photo = listing.get("has_photo")
    if photos == "yes" and has_photo is False:
        return False
    if photos == "no" and has_photo is True:
        return False
    return True


def evaluate(cfg, card, listing):
    """Returns (alert: bool, matched_words: list, reason: str)."""
    crit = cfg["criteria"]
    if not fits(listing, crit.get("languages", []), crit.get("min_condition", ""), crit.get("countries", [])):
        return False, [], "outside your Alerts criteria"
    if not fits(listing, card.get("languages", []), card.get("min_condition", ""),
                card.get("countries", []), card.get("photos", "any")):
        return False, [], "outside this card's filters"
    watch, ignore = words_for_card(cfg, card)
    comment = listing.get("comment", "")
    blocked = found_words(comment, ignore)
    if blocked:
        return False, [], "mentions " + ", ".join(blocked)
    if not watch:
        return True, [], "no keywords set: every new listing alerts you"
    hits = found_words(comment, watch)
    if hits:
        return True, hits, "mentions " + ", ".join(hits)
    return False, [], "no keyword in the comment" if comment else "no comment"


def card_url(card):
    """The card's page with its language and condition filters in the link."""
    parts = urlsplit(card["url"].strip())
    q = [(k, v) for k, v in parse_qsl(parts.query) if k not in ("language", "minCondition")]
    ids = [str(LANG_ID[l]) for l in card.get("languages", []) if l in LANG_ID]
    if ids:
        q.append(("language", ",".join(ids)))
    mc = card.get("min_condition", "")
    if mc in COND_ID:
        q.append(("minCondition", str(COND_ID[mc])))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q, safe=","), ""))


def base_url(url):
    return urlsplit(url.strip())._replace(query="", fragment="").geturl()
