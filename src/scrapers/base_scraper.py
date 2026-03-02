import logging
import os
import re
import shutil
import subprocess
import time
import random
from typing import Optional

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

_COMMON_CHROMEDRIVER_PATHS = [
    "/usr/bin/chromedriver",
    "/usr/local/bin/chromedriver",
    "/snap/bin/chromedriver",
    "/opt/homebrew/bin/chromedriver",
    "C:\\chromedriver\\chromedriver.exe",
    "C:\\Program Files\\chromedriver\\chromedriver.exe",
]

_CLOUDFLARE_MARKERS = (
    "just a moment", "cloudflare", "security verification",
    "performing security", "enable javascript and cookies",
    "ray id:",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_cloudflare_blocked(html: str) -> bool:
    if not html: return False
    snippet = html[:2000].lower()
    return any(marker in snippet for marker in _CLOUDFLARE_MARKERS)

def _get_chrome_major_version() -> Optional[int]:
    if os.name == "nt":
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for reg_path in (r"SOFTWARE\Google\Chrome\BLBeacon", r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon"):
                    try:
                        key = winreg.OpenKey(root, reg_path)
                        version, _ = winreg.QueryValueEx(key, "version")
                        return int(version.split(".")[0])
                    except: continue
        except: pass
    return None

def _resolve_chromedriver_path() -> Optional[str]:
    for path in [os.environ.get("CHROMEDRIVER_PATH"), shutil.which("chromedriver"), *_COMMON_CHROMEDRIVER_PATHS]:
        if path and os.path.isfile(path): return path
    return None

def _solve_turnstile(driver):
    try:
        wait = WebDriverWait(driver, 15)
        iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")))
        driver.switch_to.frame(iframe)
        target = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='checkbox'], #success-grid, .ctp-checksum-container")))
        time.sleep(random.uniform(2.0, 4.0))
        ActionChains(driver).move_to_element(target).move_by_offset(random.randint(-2, 2), random.randint(-2, 2)).click().perform()
        driver.switch_to.default_content()
        logger.info("[Bypass] Turnstile clicked.")
        time.sleep(5)
        return True
    except:
        driver.switch_to.default_content()
        return False

# ── Driver Builders (Public & Private) ────────────────────────────────────────

def _build_uc_driver(headless: bool, user_agent: str, chrome_version: Optional[int]):
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    if headless: options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=chrome_version)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def _build_selenium_driver(headless: bool, user_agent: str):
    path = _resolve_chromedriver_path()
    options = Options()
    if headless: options.add_argument("--headless=new")
    options.add_argument(f"--user-agent={user_agent}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(service=Service(path), options=options)

def build_driver(headless: bool = True, user_agent: Optional[str] = None, use_uc: bool = True):
    """Fungsi publik yang dibutuhkan oleh WA scraper."""
    ua = user_agent or _UA
    major = _get_chrome_major_version()
    if use_uc:
        try: return _build_uc_driver(headless, ua, major)
        except: pass
    return _build_selenium_driver(headless, ua)

# ── Fetch Strategies ──────────────────────────────────────────────────────────

def _fetch_selenium(url, headless, user_agent, wait_for_selector, wait_timeout, wait_seconds, use_uc, should_solve=False):
    driver = build_driver(headless, user_agent, use_uc)
    try:
        driver.get(url)
        if should_solve: _solve_turnstile(driver)
        if wait_for_selector:
            try: WebDriverWait(driver, wait_timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector)))
            except: pass
        time.sleep(wait_seconds)
        return driver.page_source
    finally: driver.quit()

def get_page_source(url, state="GENERIC", headless=True, wait_seconds=5, user_agent=None, wait_for_selector=None, wait_timeout=30, use_uc=True):
    state_up = state.upper()
    if state_up == "ACT":
        return _fetch_selenium(url, headless, user_agent or _UA, wait_for_selector, wait_timeout, wait_seconds, True, True)
    
    # Untuk state lain, panggil Selenium biasa (atau tambahkan curl_cffi Anda jika ada)
    return _fetch_selenium(url, headless, user_agent or _UA, wait_for_selector, wait_timeout, wait_seconds, use_uc, False)

# ── Record Builder ────────────────────────────────────────────────────────────

def make_raw_record(state, list_type, raw_code, raw_name, visa_190, visa_491, **extra_fields):
    """Fungsi publik yang dibutuhkan oleh hampir semua scraper."""
    record = {
        "state": state,
        "list_type": list_type,
        "raw_code": str(raw_code).strip() if raw_code else None,
        "raw_name": str(raw_name).strip() if raw_name else None,
        "visa_190": bool(visa_190),
        "visa_491": bool(visa_491),
    }
    record.update(extra_fields)
    return record