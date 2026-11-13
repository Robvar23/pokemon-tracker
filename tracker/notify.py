"""Sending alerts: Discord (webhook) and email (Gmail). Each returns True/False and never crashes the bot."""

import json
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BLUE = 0x0066CC


def _post_discord(webhook, payload):
    req = urllib.request.Request(
        webhook.strip(), data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "PokemonTracker (webhook, 1.0)"},
        method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return 200 <= resp.status < 300


def discord(cfg, payload, log):
    n = cfg["notify"]
    if not n.get("discord"):
        return None
    hook = n.get("discord_webhook", "").strip()
    if not hook.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/",
                            "https://ptb.discord.com/api/webhooks/", "https://canary.discord.com/api/webhooks/")):
        log("  Discord skipped: no webhook link in config.json yet")
        return False
    payload = dict(payload, username="Pokémon Tracker")
    try:
        _post_discord(hook, payload)
        log("  Discord message sent")
        return True
    except urllib.error.HTTPError as e:
        hint = {401: "the webhook link is wrong", 404: "the webhook was deleted in Discord",
                429: "Discord says slow down"}.get(e.code, "")
        log(f"  Discord failed ({e.code}{': ' + hint if hint else ''})")
    except Exception as e:  # no internet, timeout, ...
        log(f"  Discord failed: {e}")
    return False


def email(cfg, subject, body, log):
    n = cfg["notify"]
    if not n.get("email"):
        return None
    to, frm = n.get("email_to", "").strip(), n.get("email_from", "").strip()
    pw = n.get("email_app_password", "").replace(" ", "").strip()
    if not (to and frm and pw):
        log("  Email skipped: email isn't filled in in config.json")
        return False
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = frm, to, subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
            s.starttls()
            s.login(frm, pw)
            s.sendmail(frm, [a.strip() for a in to.split(",")], msg.as_string())
        log(f"  Email sent to {to}")
        return True
    except smtplib.SMTPAuthenticationError:
        log("  Email failed: Gmail rejected the login. Use a Gmail App Password, with 2-Step Verification on.")
    except Exception as e:
        log(f"  Email failed: {e}")
    return False


def _cut(text, n):
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def match_alert(cfg, card_title, listing, matched, url, carted, log):
    """Send one match to every channel that's switched on. Returns the list of channels that worked."""
    comment = listing.get("comment", "")
    fields = [
        {"name": "Price", "value": listing.get("price") or "?", "inline": True},
        {"name": "Condition", "value": " · ".join(x for x in (listing.get("condition_name"), listing.get("language")) if x) or "?", "inline": True},
        {"name": "Seller", "value": " · ".join(x for x in (listing.get("seller"), listing.get("country")) if x) or "?", "inline": True},
    ]
    if matched:
        fields.append({"name": "Keywords", "value": ", ".join(matched), "inline": False})
    if carted is not None:
        fields.append({"name": "Cart", "value": "Added to your cart" if carted else "Couldn't add it to your cart", "inline": False})
    payload = {
        "content": f"New match: **{_cut(card_title, 150)}**",
        "embeds": [{
            "title": _cut(card_title, 250), "url": url, "color": BLUE,
            "description": f"“{_cut(comment, 1000)}”" if comment else "(no seller comment)",
            "fields": fields,
            "footer": {"text": "Photos: yes" if listing.get("has_photo") else "Photos: no" if listing.get("has_photo") is False else "Pokémon Tracker"},
        }],
    }
    body = (f"New match on Cardmarket\n\nCard: {card_title}\nPrice: {listing.get('price')}\n"
            f"Condition: {listing.get('condition_name') or listing.get('condition')}\nLanguage: {listing.get('language')}\n"
            f"Seller: {listing.get('seller')} ({listing.get('country')})\nComment: {comment}\n"
            f"Keywords: {', '.join(matched) or '-'}\n"
            + ("" if carted is None else ("Added to your cart.\n" if carted else "Couldn't add it to your cart.\n"))
            + f"\nOpen it: {url}\n")
    sent = []
    if discord(cfg, payload, log):
        sent.append("Discord")
    if email(cfg, f"New match: {card_title} – {listing.get('price')}", body, log):
        sent.append("Email")
    if not sent:
        log("  Nobody was notified: switch on Discord or email in config.json")
    return sent


def status_alert(cfg, text, log):
    """For 'the bot needs you' and 'started' messages. Discord only (email would be noisy)."""
    return discord(cfg, {"content": text}, log)


def test(cfg, log):
    payload = {"content": "**Test message** from Pokémon Tracker – if this buzzes on your phone, notifications work."}
    d = discord(cfg, payload, log)
    e = email(cfg, "Pokémon Tracker test", "If you can read this, email alerts work.", log)
    return d, e
