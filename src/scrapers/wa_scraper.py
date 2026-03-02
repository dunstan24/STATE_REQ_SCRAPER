"""
WA Scraper — Western Australia State Nominated Migration Program.
"""

import csv
import io
import logging
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup, Tag as BsTag
from selenium.common.exceptions import (
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base_scraper import build_driver, make_raw_record

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SHOW_ALL_BUTTON_ID = "edit-showall"
# HANYA ambil row occupation yang merupakan direct child dan BUKAN container
OCCUPATION_ROW_CSS = "div.view-content.row > div.occupation.views-row:not(.container)"
CSV_ENDPOINT       = (
    "https://migration.wa.gov.au/v2_occupation_search/occupation-search"
    "?page&_format=csv"
)

_ANZSCO_6_RE = re.compile(r"\b(\d{6})\b")
_ANZSCO_4_RE = re.compile(r"\b(\d{4})\b")

# ── Public entry point ─────────────────────────────────────────────────────────

def scrape(url: str, state: str = "WA", list_type: str = "main",
           headless: bool = True) -> List[dict]:
    logger.info(f"[WA] Scraping {list_type} list from: {url}")

    records = _scrape_via_selenium(url, state, list_type, headless)

    if not records:
        logger.warning("[WA] Selenium scrape failed or empty. Executing CSV fallback.")
        records = _scrape_via_csv(state, list_type)

    logger.info(f"[WA] Total records extracted: {len(records)}")
    return records


# ── Selenium scraper ───────────────────────────────────────────────────────────

def _scrape_via_selenium(url: str, state: str, list_type: str,
                         headless: bool) -> List[dict]:
    driver = None
    try:
        driver = build_driver(headless=headless)
        driver.get(url)

        success = _click_show_all(driver)
        if not success:
            logger.warning("[WA] Failed to expand 'Show All'. HTML parsing may be incomplete.")

        html = driver.page_source
        return _parse_wa_html(html, state, list_type)

    except Exception as exc:
        logger.error(f"[WA] Selenium scrape failed: {exc}")
        return []
    finally:
        if driver:
            time.sleep(1)
            driver.quit()


# ── Click Show All ─────────────────────────────────────────────────────────────

def _dismiss_overlays(driver) -> None:
    selectors = [
        "button[id*='cookie'][id*='accept']",
        "button[class*='cookie'][class*='accept']",
        "button[aria-label*='Accept']",
        "button[aria-label*='accept']",
        "button.modal-close",
        "button[data-dismiss='modal']",
        "[id*='onetrust-accept']",
        ".cc-accept",
    ]
    for sel in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.5)
        except Exception:
            pass

def _get_row_count(driver) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, OCCUPATION_ROW_CSS))

def _click_show_all(driver) -> bool:
    MAX_CLICK_RETRIES = 3
    WAIT_FOR_BTN_SEC  = 15
    WAIT_FOR_ROWS_SEC = 30

    _dismiss_overlays(driver)

    baseline_count = _get_row_count(driver)
    logger.info(f"[WA] Baseline rows before click: {baseline_count}")

    try:
        WebDriverWait(driver, WAIT_FOR_BTN_SEC).until(
            EC.presence_of_element_located((By.ID, SHOW_ALL_BUTTON_ID))
        )
    except TimeoutException:
        logger.warning("[WA] Show All button not found.")
        return False

    clicked = False
    for attempt in range(1, MAX_CLICK_RETRIES + 1):
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, SHOW_ALL_BUTTON_ID))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'});", btn)
            time.sleep(0.5)
            
            # Eksekusi klik langsung via JS untuk meminimalisir interupsi overlay
            driver.execute_script("arguments[0].click();", btn)
            clicked = True
            break
        except Exception as exc:
            logger.warning(f"[WA] Click attempt {attempt} failed: {exc}")
            _dismiss_overlays(driver)
            time.sleep(1)

    if not clicked:
        logger.error("[WA] Exhausted all click retries.")
        return False

    # Tunggu secara cerdas hingga jumlah baris membesar melampaui baseline (AJAX selesai)
    try:
        WebDriverWait(driver, WAIT_FOR_ROWS_SEC).until(
            lambda d: _get_row_count(d) > baseline_count
        )
        final_count = _get_row_count(driver)
        logger.info(f"[WA] AJAX complete. Rows stabilized at: {final_count}")
        return True
    except TimeoutException:
        logger.warning("[WA] Timed out waiting for rows to increase after click.")
        return False


# ── HTML Parser ────────────────────────────────────────────────────────────────

def _parse_wa_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []

    # FIX: Jangan cuma select_one. Cari view-content row yang BENAR,
    # yang terbukti mengandung class occupation.
    walk_target = None
    for container in soup.select("div.view-content.row"):
        if container.select_one("div.occupation.views-row"):
            walk_target = container
            break

    if not walk_target:
        logger.error("[WA] FATAL: Valid 'div.view-content.row' containing occupations not found. Forcing CSV fallback.")
        return []

    current_category = None
    for child in walk_target.children:
        if not isinstance(child, BsTag):
            continue

        if child.name == "h3":
            current_category = child.get_text(strip=True)
            continue

        if child.name == "div":
            classes = set(child.get("class", []))
            if "occupation" in classes and "views-row" in classes and "container" not in classes:
                record = _extract_row_data(child, state, list_type, current_category)
                if record:
                    records.append(record)

    return records

def _extract_row_data(row, state: str, list_type: str, category: Optional[str]) -> Optional[dict]:
    btn = row.select_one("button.accordion-button")
    occupation_name, stream = None, None
    if btn:
        p1 = btn.select_one("span.part1")
        p2 = btn.select_one("span.part2")
        occupation_name = p1.get_text(strip=True) if p1 else None
        stream          = p2.get_text(strip=True) if p2 else None

    body = row.select_one("div.accordion-body")
    anzsco_code, min_points, status = None, None, None
    visa_190, visa_491 = False, False

    if body:
        for item in body.select("span.v2-occupation-item"):
            text = item.get_text(separator=" ", strip=True)

            if "ANZSCO" in text and not anzsco_code:
                m = _ANZSCO_6_RE.search(text) or _ANZSCO_4_RE.search(text)
                anzsco_code = m.group(1) if m else None

            if "Minimum Points" in text and min_points is None:
                m = re.search(r"Minimum Points[:\s]+(\d+)", text)
                if m: min_points = int(m.group(1))

            if "Status" in text and status is None:
                m = re.search(r"Status[:\s]+(.+)", text)
                if m: status = m.group(1).strip()

        for bold in body.find_all("b"):
            bold_text = bold.get_text(strip=True)
            next_val  = _get_next_text(bold)

            if "Visa V190" in bold_text: visa_190 = _parse_yes_no(next_val)
            elif "Visa V491" in bold_text: visa_491 = _parse_yes_no(next_val)

        if not visa_190 and not visa_491:
            body_text = body.get_text(separator=" ")
            visa_190 = bool(re.search(r"Visa\s+V?190[:\s]+Yes", body_text, re.IGNORECASE))
            visa_491 = bool(re.search(r"Visa\s+V?491[:\s]+Yes", body_text, re.IGNORECASE))

    if not occupation_name and not anzsco_code:
        return None

    return make_raw_record(
        state=state,
        list_type=list_type,
        raw_code=anzsco_code,
        raw_name=occupation_name,
        visa_190=visa_190,
        visa_491=visa_491,
        stream=stream,
        min_points=min_points,
        status=status,
        category=category,
    )

def _get_next_text(tag) -> str:
    sibling = tag.next_sibling
    while sibling is not None:
        text = sibling.get_text(strip=True) if isinstance(sibling, BsTag) else str(sibling).strip()
        if text: return text
        sibling = sibling.next_sibling
    return ""

def _parse_yes_no(text: str) -> bool:
    return text.strip().lower() in {"yes", "y", "1", "true", "eligible"}


# ── CSV endpoint fallback ──────────────────────────────────────────────────────

def _scrape_via_csv(state: str, list_type: str) -> List[dict]:
    logger.info(f"[WA] Downloading CSV fallback: {CSV_ENDPOINT}")
    records = []
    try:
        resp = requests.get(CSV_ENDPOINT, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}, timeout=30)
        resp.raise_for_status()

        # FIX: Validasi jika yang dikembalikan adalah halaman blokir HTML bot
        if "<html" in resp.text.lower() or "<body" in resp.text.lower():
            logger.error("[WA] CSV fallback gagal: Endpoint dikembalikan sebagai halaman HTML (Kemungkinan diblokir Anti-Bot/Cloudflare).")
            return []

        reader = csv.DictReader(io.StringIO(resp.text))
        
        for row in reader:
            raw_code = _find_in_row(row, ["anzsco", "code"])
            raw_name = _find_in_row(row, ["occupation", "title", "name"])
            v190_val = _find_in_row(row, ["190"])
            v491_val = _find_in_row(row, ["491"])
            
            # Coba amankan data kategori jika tersedia di header CSV
            category_val = _find_in_row(row, ["category", "industry", "group"])

            if raw_code:
                m = _ANZSCO_6_RE.search(raw_code)
                raw_code = m.group(1) if m else raw_code.strip()

            visa_190 = _csv_is_eligible(v190_val)
            visa_491 = _csv_is_eligible(v491_val)

            if v190_val is None and v491_val is None:
                visa_190 = True

            if raw_code or raw_name:
                records.append(make_raw_record(
                    state=state,
                    list_type=list_type,
                    raw_code=raw_code,
                    raw_name=raw_name,
                    visa_190=visa_190,
                    visa_491=visa_491,
                    category=category_val, # Sinkronisasi skema data
                ))

    except Exception as exc:
        logger.error(f"[WA] CSV fallback failed: {exc}")

    return records

def _find_in_row(row: dict, keywords: list) -> Optional[str]:
    for key, val in row.items():
        if any(kw in key.lower() for kw in keywords):
            return val.strip() if val else None
    return None

def _csv_is_eligible(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"yes", "y", "1", "true", "eligible"}