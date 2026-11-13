"""Everything that touches the Cardmarket website (through Chrome)."""

import os
import re
import subprocess
import sys
import time

import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .matching import COND_NAMES, condition_code, language_name

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# --------------------------------------------------------------------------- #
# Chrome
# --------------------------------------------------------------------------- #
def detect_chrome_major_version():
    if sys.platform.startswith("win"):
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for path in (r"Software\Google\Chrome\BLBeacon", r"Software\WOW6432Node\Google\Chrome\BLBeacon"):
                    try:
                        with winreg.OpenKey(hive, path) as key:
                            version, _ = winreg.QueryValueEx(key, "version")
                            return int(str(version).split(".")[0])
                    except OSError:
                        continue
        except Exception:
            pass
        for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            app_dir = os.path.join(base, "Google", "Chrome", "Application")
            if os.path.isdir(app_dir):
                for name in os.listdir(app_dir):
                    m = re.match(r"^(\d+)\.\d+\.\d+\.\d+$", name)
                    if m:
                        return int(m.group(1))
        return None
    candidates = [MAC_CHROME, os.path.expanduser("~" + MAC_CHROME)] if sys.platform == "darwin" else []
    candidates += ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
    for exe in candidates:
        try:
            out = subprocess.check_output([exe, "--version"], text=True, timeout=10)
            m = re.search(r"(\d+)\.\d+", out)
            if m:
                return int(m.group(1))
        except Exception:
            continue
    return None


def start_browser(cfg, profile_dir, log):
    v = str(cfg.get("chrome_version", "")).strip()
    version_main = int(v) if v.isdigit() else detect_chrome_major_version()
    log(f"Using Chrome version {version_main}" if version_main else
        "Couldn't detect your Chrome version; letting the driver guess. If Chrome won't start, "
        "put your Chrome version number in config.json at \"chrome_version\".")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    # A Chrome profile of its own, so the Cardmarket login is remembered between runs.
    driver = uc.Chrome(options=options, version_main=version_main, use_subprocess=True, user_data_dir=profile_dir)
    driver.set_page_load_timeout(60)
    return driver


def dismiss_cookie_banner(driver):
    for xpath in (
        "//button[contains(@class,'btn') and (contains(.,'Accept') or contains(.,'Akzeptieren') "
        "or contains(.,'Accepteren') or contains(.,'Accepter') or contains(.,'Aceptar'))]",
        "//*[@id='CookiesConsent']//button",
    ):
        try:
            for btn in driver.find_elements(By.XPATH, xpath):
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    return
        except WebDriverException:
            pass


def is_logged_in(driver):
    try:
        if driver.find_elements(By.XPATH, "//a[contains(@href,'/Logout') or contains(@href,'logout')]"):
            return True
        return not driver.find_elements(By.XPATH, "//input[@name='username']")
    except WebDriverException:
        return False


def login(driver, username, password, log, ask_for_help):
    driver.get("https://www.cardmarket.com/en/Pokemon")
    time.sleep(3)
    dismiss_cookie_banner(driver)
    if is_logged_in(driver):
        log("Already logged in to Cardmarket.")
        return
    if username and password:
        try:
            user_box = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@name='username']")))
            pass_box = driver.find_element(By.XPATH, "//input[@type='password']")
            user_box.clear(); user_box.send_keys(username)
            pass_box.clear(); pass_box.send_keys(password)
            driver.find_element(By.XPATH, "//input[@name='username']/ancestor::form//*[(@type='submit')]").click()
            time.sleep(5)
        except (TimeoutException, NoSuchElementException):
            log("Couldn't find the login form (maybe a captcha / Cloudflare check).")
    if not is_logged_in(driver):
        ask_for_help()
    log("Logged in.")


# --------------------------------------------------------------------------- #
# Reading a card page
# --------------------------------------------------------------------------- #
LABEL_ATTRS = ("aria-label", "data-bs-original-title", "data-original-title", "title")


def _attr(el, names=LABEL_ATTRS):
    for n in names:
        try:
            v = el.get_attribute(n)
            if v and v.strip():
                return v.strip()
        except WebDriverException:
            pass
    return ""


def _labels(row):
    """Every tooltip / aria-label inside the row (icons for language, location, photo, ...)."""
    out = []
    try:
        for el in row.find_elements(By.XPATH, ".//*[@aria-label or @data-bs-original-title or @data-original-title or @title]"):
            t = _attr(el)
            if t:
                out.append((el, t))
    except WebDriverException:
        pass
    return out


LOAD_MORE = "//button[@id='loadMoreButton' or contains(.,'Show more results') or contains(.,'Load more')]"


def press_load_more(driver, times, log):
    for _ in range(max(0, int(times or 0))):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        try:   # the button can take a moment to appear after the page loads
            WebDriverWait(driver, 8).until(lambda d: any(b.is_displayed() for b in d.find_elements(By.XPATH, LOAD_MORE)))
        except TimeoutException:
            return
        btns = [b for b in driver.find_elements(By.XPATH, LOAD_MORE) if b.is_displayed()]
        if not btns:
            return
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btns[0])
            time.sleep(1)
            before = len(driver.find_elements(By.XPATH, "//div[contains(@class,'article-row')]"))
            btns[0].click()
            WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(By.XPATH, "//div[contains(@class,'article-row')]")) > before)
            time.sleep(1)
        except (WebDriverException, TimeoutException):
            return


def page_title(driver, fallback):
    try:
        return " ".join(driver.find_element(By.XPATH, "//h1").text.split()) or fallback
    except NoSuchElementException:
        return fallback


def get_rows(driver):
    WebDriverWait(driver, 20).until(EC.presence_of_element_located(
        (By.XPATH, "//div[contains(@class,'article-row')] | //div[contains(@class,'table-body')]")))
    return (driver.find_elements(By.XPATH, "//div[contains(@class,'table-body')]//div[contains(@class,'article-row')]")
            or driver.find_elements(By.XPATH, "//div[contains(@class,'article-row')]"))


def _comment(row):
    texts = []
    # Only the seller-comment part of the row; never the condition / language / price columns.
    for xp in (".//div[contains(@class,'product-comments')]",
               ".//*[contains(@class,'product-comments')]//span",
               ".//*[contains(@class,'comment') and not(contains(@class,'condition'))]"):
        try:
            for el in row.find_elements(By.XPATH, xp):
                t = " ".join((el.get_attribute("textContent") or "").split())
                tip = _attr(el)
                for cand in (t, tip):
                    if cand and len(cand) > 1:
                        texts.append(cand)
        except WebDriverException:
            pass
    # Never let a condition or language label count as a comment.
    labels = {n.lower() for n in COND_NAMES.values()} | {c.lower() for c in COND_NAMES}
    texts = [t for t in texts if t.lower() not in labels and not language_name(t)]
    # The full comment is the longest text we found (the visible one may be cut off with "...").
    return max(texts, key=len) if texts else ""


def read_listing(row):
    d = {"id": "", "price": "", "seller": "", "seller_link": "", "country": "", "language": "",
         "condition": "", "condition_name": "", "comment": "", "has_photo": None}
    try:
        d["id"] = row.get_attribute("id") or ""
    except WebDriverException:
        pass
    try:
        cond = row.find_element(By.XPATH, ".//a[contains(@class,'article-condition')] | .//span[contains(@class,'article-condition')]")
        raw = _attr(cond) or cond.text.strip()
        code = condition_code(raw) or condition_code(cond.text.strip())
        d["condition"], d["condition_name"] = code, COND_NAMES.get(code, raw)
    except NoSuchElementException:
        pass
    try:
        d["price"] = " ".join(row.find_element(By.XPATH, ".//div[contains(@class,'price-container')]").text.split())
    except NoSuchElementException:
        pass
    try:
        seller = row.find_element(By.XPATH, ".//span[contains(@class,'seller-name')]")
        d["seller"] = seller.text.strip()
        try:
            d["seller_link"] = seller.find_element(By.XPATH, ".//a").get_attribute("href") or ""
        except NoSuchElementException:
            pass
    except NoSuchElementException:
        pass
    photo_seen = False
    for el, label in _labels(row):
        low = label.lower()
        if not d["country"] and "location" in low:
            d["country"] = label.split(":", 1)[-1].strip()
        elif not d["language"] and language_name(label):
            d["language"] = language_name(label)
        if any(w in low for w in ("image", "photo", "picture", "scan")):
            photo_seen = True
    if not photo_seen:
        try:
            photo_seen = bool(row.find_elements(
                By.XPATH, ".//*[contains(@class,'camera') or contains(@class,'fonticon-image') or @data-img or contains(@data-bs-content,'<img')]"))
        except WebDriverException:
            pass
    d["has_photo"] = photo_seen
    d["comment"] = _comment(row)
    return d


def listing_key(d, title):
    return d["id"] or "|".join([title, d["seller"], d["price"], d["condition"], d["comment"][:40]])


def add_to_cart(driver, row):
    btn = row.find_element(
        By.XPATH, ".//button[@type='submit' and (contains(@aria-label,'cart') or contains(@aria-label,'Cart') "
                  "or contains(@title,'cart') or contains(@class,'btn-cart'))]")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(1)
    btn.click()
