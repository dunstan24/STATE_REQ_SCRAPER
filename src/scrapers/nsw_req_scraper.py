""" NSW State Visa Requirements Scraper

Alur kerja Function:

__main__
  ├── scrape_nsw_subclass(190, url_190, ...)
  │     ├── fetch_and_parse(url)                   → BeautifulSoup container (nsw-layout__main)
  │     ├── extract_wysiwyg_by_keyword(container)  → teks dari nsw-wysiwyg-content (General Req)
  │     ├── extract_li_from_wysiwyg(container)     → teks dari <li> spesifik (State / Overseas)
  │     └── extract_service_fee_from_soup(soup)    → list nilai $xxx dari <li> "service fee"
  │
  ├── scrape_nsw_subclass(491, url_491, ...)       → sama seperti di atas untuk subclass 491
  │
  ├── pd.concat([df_190, df_491])                  → gabung jadi 1 DataFrame (2 baris)
  │
  └── export_dataframe(final_df, ...)              → CSV + JSON + formatted XLSX
"""

import logging
import os

import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright
from general_tools_scrap import (
    get_clean_text,
    format_li,
    extract_service_fee,
    export_dataframe
)

# Output path relative to this script location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "nsw")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)



def fetch_and_parse(url, selector=".nsw-layout__main"):
    """Fetch HTML dan return BeautifulSoup container"""
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url, wait_for_selector=selector, extra_wait_seconds=3, bypass_cf=False
    )
    if not html:
        logger.error("Gagal mendapatkan HTML. Cloudflare mungkin memblokir.")
        return None

    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", {"id": "main", "class": "nsw-layout__main"})
    if not container:
        container = soup.find("div", class_="nsw-layout__main")
    return container




def extract_wysiwyg_by_keyword(container, keyword):
    """Cari div.nsw-wysiwyg-content yang mengandung *keyword*,
    lalu ekstrak seluruh teks bersih dari div tersebut.

    Strategi pencarian:
      1. Cek teks awal (200 char) setiap nsw-wysiwyg-content
      2. Fallback: cari heading (h2/h3/h4) -> ambil wysiwyg-content berikutnya
    """
    if not container or not keyword:
        return ""

    wysiwyg_divs = container.find_all("div", class_="nsw-wysiwyg-content")
    logger.info(f"Ditemukan {len(wysiwyg_divs)} div.nsw-wysiwyg-content")

    # Strategy 1: match directly in the initial text of the div
    for div in wysiwyg_divs:
        preview = div.get_text(" ", strip=True)[:200]
        if keyword.lower() in preview.lower():
            logger.info(f"Matched wysiwyg-content: '{keyword}' → {preview[:80]}...")
            return get_clean_text(div)

    # Strategy 2: find heading that contains the keyword
    for heading in container.find_all(["h2", "h3", "h4"]):
        if keyword.lower() in heading.get_text(strip=True).lower():
            sibling = heading.find_next("div", class_="nsw-wysiwyg-content")
            if sibling:
                logger.info(
                    f"Matched via heading '{heading.get_text(strip=True)}' "
                    f"→ wysiwyg-content berikutnya"
                )
                return get_clean_text(sibling)

    logger.warning(f"Tidak ditemukan wysiwyg-content dengan keyword '{keyword}'")
    return ""


def extract_li_from_wysiwyg(container, li_keyword, wysiwyg_keyword=None):
    """Cari <li> di dalam div.nsw-wysiwyg-content yang mengandung *li_keyword*,
    lalu return teks dari <li> tersebut (termasuk nested sub-poin).

    Prioritas pencarian: leaf <li> (tanpa nested ul/ol) lebih diutamakan
    daripada parent <li>, agar tidak salah match parent yang teks get_text()-nya
    mencakup semua child.

    Parameters
    ----------
    container       : BeautifulSoup element (nsw-layout__main)
    li_keyword      : str — teks yang dicari di dalam <li>
    wysiwyg_keyword : str | None — jika diisi, hanya cari di nsw-wysiwyg-content
                      yang mengandung teks ini (misal 'Residency').
                      Jika None, cari di semua nsw-wysiwyg-content.
    """
    if not container or not li_keyword:
        return ""

    wysiwyg_divs = container.find_all("div", class_="nsw-wysiwyg-content")

    # Filter wysiwyg div jika wysiwyg_keyword diberikan
    if wysiwyg_keyword:
        wysiwyg_divs = [
            div for div in wysiwyg_divs
            if wysiwyg_keyword.lower() in div.get_text(" ", strip=True).lower()
        ]
        if not wysiwyg_divs:
            logger.warning(
                f"Tidak ditemukan wysiwyg-content dengan teks '{wysiwyg_keyword}'"
            )
            return ""

    for div in wysiwyg_divs:
        all_lis = div.find_all("li")

        # Pass 1: cari di leaf <li> dulu (tanpa nested ul/ol)
        for li in all_lis:
            if li.find(["ul", "ol"]):
                continue  # skip parent <li>
            li_text = li.get_text(" ", strip=True)
            if li_keyword.lower() in li_text.lower():
                logger.info(f"Matched leaf <li>: '{li_keyword}' → {li_text[:80]}...")
                return li_text

        # Pass 2: fallback ke parent <li> jika leaf tidak match
        for li in all_lis:
            li_text = li.get_text(" ", strip=True)
            if li_keyword.lower() in li_text.lower():
                logger.info(f"Matched parent <li>: '{li_keyword}' → {li_text[:80]}...")
                return format_li(li)

    logger.warning(f"Tidak ditemukan <li> dengan keyword '{li_keyword}'")
    return ""


def extract_service_fee_from_soup(soup):
    """Wrapper untuk extract_service_fee"""
    return extract_service_fee(soup)


# ── Scraper Utama ─────────────────────────────────────────────────────────────

def scrape_nsw_subclass(subclass, url, kw_general, kw_details):
    """Scrape NSW visa requirements untuk satu subclass.

    Parameters
    ----------
    subclass   : int — 190 atau 491
    url        : str — URL halaman NSW
    kw_general : str — keyword wysiwyg-content untuk General Requirements
    kw_details : list[str] — list keyword wysiwyg-content yang digabung
                 menjadi Detail Requirements
    """
    logger.info(f"=== Scraping NSW Subclass {subclass} ===")
    soup = fetch_and_parse(url)

    # General Requirements
    text_general = extract_wysiwyg_by_keyword(soup, kw_general)

    # Detail Requirements — gabung teks dari beberapa wysiwyg-content
    detail_parts = []
    for kw in kw_details:
        text = extract_wysiwyg_by_keyword(soup, kw)
        if text:
            detail_parts.append(text)
    text_detail = "\n\n".join(detail_parts)

    data = {
        "state code": "NSW",
        "state stream": str(subclass),
        "General Requirements": text_general,
        "Detail Requirements": text_detail,
    }

    return pd.DataFrame([data])


# ── Export ────────────────────────────────────────────────────────────────────

def export_results(df):
    """Export hasil scraping NSW ke CSV, JSON, dan formatted XLSX."""
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_nsw",
        preview_columns=["state code", "state stream"],
    )

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # ── Subclass 190 ──────────────────────────────────────────────────────
    # General Requirements : wysiwyg "Basic Eligibility"
    # Detail Requirements  : wysiwyg "Key Steps..." + "Understanding Invitation Rounds..."
    df_190 = scrape_nsw_subclass(
        subclass=190,
        url="https://www.nsw.gov.au/visas-and-migration/skilled-visas/skilled-nominated-visa-subclass-190",
        kw_general="Basic Eligibility",
        kw_details=[
            "Key Steps for Securing NSW Nomination",
            "Understanding Invitation Rounds and the NSW Skills List",
        ],
    )

    # ── Subclass 491 ──────────────────────────────────────────────────────
    # General Requirements : wysiwyg "About NSW Nomination"
    # Detail Requirements  : wysiwyg "Understanding Invitation Rounds..." + "Key Steps..."
    df_491 = scrape_nsw_subclass(
        subclass=491,
        url="https://www.nsw.gov.au/visas-and-migration/skilled-visas/skilled-work-regional-visa-subclass-491",
        kw_general="About NSW Nomination",
        kw_details=[
            "Understanding Invitation Rounds and the NSW Regional Skills List",
            "Key Steps for Securing NSW Nomination",
        ],
    )

    # Gabungkan & export
    final_df = pd.concat([df_190, df_491], ignore_index=True)
    export_results(final_df)
