"""The main loop: check every watched card, alert on new listings that fit, repeat."""

import json
import os
import random
import time
import traceback
from datetime import datetime

from selenium.common.exceptions import TimeoutException, WebDriverException

from . import cardmarket as cm
from . import notify
from .config import APP_DIR, load_config
from .matching import base_url, card_url, evaluate

STATE_FILE = os.path.join(APP_DIR, "state.json")
LOG_FILE = os.path.join(APP_DIR, "tracker.log")
PROFILE_DIR = os.path.join(APP_DIR, "chrome-profile")


def log(text):
    line = f"{datetime.now():%H:%M:%S} {text}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d} {line}\n")
    except OSError:
        pass


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    s.setdefault("seen", {})
    s.setdefault("matches", [])
    return s


def save_state(state):
    for k, v in state["seen"].items():
        state["seen"][k] = v[-3000:]
    state["matches"] = state["matches"][-300:]
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def ask_for_help(cfg):
    def _ask():
        notify.status_alert(cfg, "⚠️ **Pokémon Tracker needs you:** Cardmarket wants you to log in by hand "
                                 "(probably a captcha). Log in in the tracker's Chrome window, then press Enter "
                                 "in the tracker window.", log)
        print("\n>>> Please log in to Cardmarket by hand in the Chrome window,")
        input(">>> then come back here and press Enter to continue... ")
    return _ask


def check_card(driver, cfg, card, state):
    url = card_url(card)
    key = base_url(card["url"])
    driver.get(url)
    time.sleep(3)
    cm.dismiss_cookie_banner(driver)
    driver.execute_script("window.scrollBy(0, 1000);")
    time.sleep(2)
    cm.press_load_more(driver, cfg.get("load_more_presses", 0), log)
    title = card.get("name") or cm.page_title(driver, card["url"])

    try:
        rows = cm.get_rows(driver)
    except TimeoutException:
        log(f"  {title}: no listings found (no offers that fit, or the page layout changed)")
        return

    first_time = key not in state["seen"]
    seen = set(state["seen"].get(key, []))
    seen_list = state["seen"].setdefault(key, [])
    with_comment = new = alerts = 0
    cart_default = bool(cfg.get("default_add_to_cart"))
    to_cart = cart_default if card.get("add_to_cart") is None else bool(card["add_to_cart"])

    for row in rows:
        try:
            d = cm.read_listing(row)
        except WebDriverException as e:
            log(f"  Skipped a listing I couldn't read ({e.__class__.__name__})")
            continue
        if d["comment"]:
            with_comment += 1
        k = cm.listing_key(d, title)
        if k in seen:
            continue
        seen.add(k)
        seen_list.append(k)
        if first_time and not cfg.get("alert_existing_on_start"):
            continue
        new += 1
        ok, matched, reason = evaluate(cfg, card, d)
        summary = f"{d['price']} | {d['condition'] or '?'} | {d['language'] or '?'} | {d['seller']} ({d['country'] or '?'})"
        if not ok:
            log(f"  New listing, no alert ({reason}): {summary}")
            continue
        alerts += 1
        log(f"  MATCH: {summary} | \"{d['comment']}\"")
        carted = None
        if to_cart:
            try:
                cm.add_to_cart(driver, row)
                carted = True
                log("  Added to cart.")
            except Exception as e:
                carted = False
                log(f"  Couldn't add to cart ({e.__class__.__name__})")
        sent = notify.match_alert(cfg, title, d, matched, url, carted, log)
        state["matches"].append({"time": datetime.now().isoformat(timespec="seconds"), "card": title,
                                 "url": url, "listing": d, "keywords": matched, "carted": carted, "sent": sent})

    note = " (first look: remembering what's already listed)" if first_time and not cfg.get("alert_existing_on_start") else ""
    log(f"  {title}: {len(rows)} listings, {with_comment} with a comment, {new} new, {alerts} matches{note}")


def run():
    cfg, note = load_config()
    if note:
        log(note)
    if not cfg["cards"]:
        log("No cards to watch yet. Add your Cardmarket card links to \"cards\" in config.json "
            "(see the README), then start the tracker again.")
        input("Press Enter to close...")
        return

    state = load_state()
    log(f"Watching {len(cfg['cards'])} card(s). Keywords: {', '.join(cfg['keywords']['watch']) or '(none: every new listing alerts you)'}")
    notify.status_alert(cfg, f"✅ Pokémon Tracker started: watching {len(cfg['cards'])} card(s).", log)

    d = cfg["delays"]
    driver, rounds = None, 0
    while True:
        try:
            if driver is None:
                driver = cm.start_browser(cfg, PROFILE_DIR, log)
                cm.login(driver, cfg["cardmarket"].get("username", ""), cfg["cardmarket"].get("password", ""),
                         log, ask_for_help(cfg))
            rounds += 1
            log(f"=== Round {rounds} ===")
            for i, card in enumerate(cfg["cards"]):
                try:
                    check_card(driver, cfg, card, state)
                except TimeoutException:
                    log(f"  Page timed out: {card['url']}")
                save_state(state)
                if i < len(cfg["cards"]) - 1:
                    time.sleep(random.randint(int(d["page_min"]), int(d["page_max"])))
            wait = random.randint(int(d["round_min"]), int(d["round_max"]))
            log(f"Sleeping for {wait} seconds before the next round...")
            time.sleep(wait)
            cfg, _ = load_config()   # pick up edits to config.json without restarting
        except KeyboardInterrupt:
            log("Stopping.")
            break
        except WebDriverException as e:
            first = str(e).splitlines()[0] if str(e) else ""
            log(f"Browser problem ({e.__class__.__name__}): {first}. Restarting Chrome in 30 seconds...")
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            driver = None
            time.sleep(30)
        except Exception:
            traceback.print_exc()
            log("Unexpected error - trying again in 60 seconds...")
            time.sleep(60)
    try:
        if driver:
            driver.quit()
    except Exception:
        pass


def test_notifications():
    cfg, note = load_config()
    if note:
        log(note)
    d, e = notify.test(cfg, log)
    if d is None and e is None:
        log("Discord and email are both switched off in config.json.")
