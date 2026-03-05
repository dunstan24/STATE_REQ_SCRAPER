""" SA State Visa Requirements Scraper

Alur kerja Function:

__main__
  ├── scrape_sa_pathway("Skilled_Employment_in_South_Australia", url)
  │     ├── fetch_and_parse(url)                       → BeautifulSoup soup
  │     ├── extract_detail_requirements(soup, url)     → teks requirements
  │     └── extract_service_fee(soup)                  → list nilai $xxx
  │
  ├── scrape_sa_pathway("South_Australian_Graduates", url)
  ├── scrape_sa_pathway("Outer_Regional_Skilled_Employment", url)
  │
  ├── scrape_sa_offshore(url)                          → 1 baris (Playwright tab-click)
  │     ├── Playwright click each tab button
  │     ├── extract content per tab
  │     └── extract_service_fee(soup)
  │
  ├── pd.concat([...])                                 → gabung jadi 1 DataFrame (4 baris)
  │
  └── export_dataframe(final_df, ...)                  → CSV + JSON + formatted XLSX
"""

import logging
import os
import re

import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright
from general_tools_scrap import (
    get_clean_text,
    extract_service_fee,
    export_dataframe,
)


# ==========================
# LINK SA
# ==========================
URL_SA_EMPLOYMENT = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/skilled-employment-in-south-australia"
URL_SA_GRADUATES = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/south-australian-graduates"
URL_SA_OUTER = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/outer-regional-skilled-employment"
URL_SA_OFFSHORE = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/moving-to-south-australia-from-overseas"
# ==========================

# Output path relative to this script location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "sa")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ── Fetch ─────────────────────────────────────────────────────────────────────


def fetch_and_parse(url):
    """Fetch HTML dan return BeautifulSoup soup.

    Parameters
    ----------
    url : str — URL halaman SA
    """
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url,
        wait_for_selector="body",
        extra_wait_seconds=3,
        bypass_cf=False,
    )
    if not html:
        logger.error("Gagal mendapatkan HTML.")
        return None

    return BeautifulSoup(html, "lxml")


# ── Parsing Helpers ───────────────────────────────────────────────────────────


_SKIP_KEYWORDS = [
    "NOMINATION PROCESS",
    "SKILLED MIGRANTS",
    "GRADUATES WHO ACHIEVE",
    "INVITATIONS TO APPLY",
]


def _extract_standard(soup):
    """Ekstrak requirements dari halaman Employment dan Graduates.

    Struktur HTML:  div.col-span-full > h2.t-heading + div.t-copy > li
    """
    lines = []
    sections = soup.find_all("div", class_="col-span-full")
    current_heading = None

    for section in sections:
        title_tag = section.find("h2", class_="t-heading")

        if title_tag:
            title = title_tag.get_text(strip=True)
            if any(skip in title.upper() for skip in _SKIP_KEYWORDS):
                continue
            current_heading = title
            lines.append(f"\n{title.upper()}")

        content = section.find("div", class_="t-copy")
        if content and current_heading:
            for li in content.find_all("li"):
                text = li.get_text(" ", strip=True)
                if text:
                    lines.append(f"- {text}")

    return "\n".join(lines).strip()


def _extract_outer_regional(soup):
    """Ekstrak requirements dari halaman Outer Regional.

    Struktur: h2 "Eligibility guidelines" → sibling l-grid-contained → t-copy > ul > li
    """
    lines = []
    all_h2 = soup.find_all("h2", class_="t-heading")
    target_heading = None

    for h2 in all_h2:
        if "Eligibility guidelines" in h2.get_text(strip=True):
            target_heading = h2
            break

    if target_heading:
        title = target_heading.get_text(strip=True)
        lines.append(f"\n{title.upper()}")

        parent_container = target_heading.find_parent("div", class_="l-grid-contained")
        if parent_container:
            next_container = parent_container.find_next_sibling(
                "div", class_="l-grid-contained"
            )
            if next_container:
                t_copy_list = next_container.find_all("div", class_="t-copy")
                for t_copy in t_copy_list:
                    for ul in t_copy.find_all("ul"):
                        for li in ul.find_all("li", recursive=False):
                            text = li.get_text(" ", strip=True)
                            if text:
                                lines.append(f"- {text}")

    return "\n".join(lines).strip()


def extract_detail_requirements(soup, url):
    """Ekstrak detail requirements berdasarkan URL halaman SA.

    Parameters
    ----------
    soup : BeautifulSoup — full page soup
    url  : str — URL halaman, menentukan logika parsing yang digunakan

    Returns
    -------
    str — teks requirements multi-line
    """
    if not soup:
        return ""

    if URL_SA_OUTER in url:
        return _extract_outer_regional(soup)

    # Standard: Employment & Graduates
    return _extract_standard(soup)


# ── Scraper Utama ─────────────────────────────────────────────────────────────


def scrape_sa_pathway(stream_name, url):
    """Scrape SA visa requirements untuk satu pathway (non-offshore).

    Parameters
    ----------
    stream_name : str — nama pathway (misal: "Skilled_Employment_in_South_Australia")
    url         : str — URL halaman SA

    Returns
    -------
    pd.DataFrame — 1 baris dengan kolom:
        state code, state stream, Detail Requirements, service fee
    """
    logger.info(f"=== Scraping SA: {stream_name} ===")
    soup = fetch_and_parse(url)
    if not soup:
        return pd.DataFrame()

    text_detail = extract_detail_requirements(soup, url)

    fees = extract_service_fee(soup, keywords=["service fee", "application fee"])
    service_fee_val = ", ".join(sorted(set(fees))) if fees else "-"

    data = {
        "state code": "SA",
        "state stream": stream_name,
        "Detail Requirements": text_detail,
        "service fee": service_fee_val,
    }

    return pd.DataFrame([data])


def scrape_sa_offshore(url):
    """Scrape halaman SA offshore (tab-click mode via Playwright).

    Offshore page menggunakan JS tab panel — konten hanya terlihat setelah
    mengklik setiap heading button. Menggunakan Playwright untuk:
      1. Load page
      2. Klik setiap tab button: div[data-tab-btn] > button
      3. Snapshot DOM setelah klik
      4. Ekstrak heading + konten dari panel yang aktif

    Returns
    -------
    pd.DataFrame — 1 baris dengan kolom:
        state code, state stream, Detail Requirements, service fee
    """
    logger.info(f"=== Scraping SA: Moving_to_South_Australia_from_Overseas ===")
    logger.info(f"Fetching offshore (tab-click mode): {url}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright tidak terinstall.")
        return pd.DataFrame()

    all_lines = []
    all_fees = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # Collect all heading buttons in DOM order
        tab_buttons = page.query_selector_all("div[data-tab-btn] button")

        for btn in tab_buttons:
            # Get heading text from <span class="z-10"> inside the button
            span = btn.query_selector("span.z-10")
            if not span:
                continue
            heading_text = span.inner_text().strip()
            if not heading_text:
                continue

            # Click to activate the tab panel
            btn.click()
            page.wait_for_timeout(600)

            # Get numeric id from the parent div[data-tab-btn]
            tab_id = btn.evaluate(
                "el => el.closest('[data-tab-btn]').getAttribute('id')"
            )

            # Snapshot DOM after click
            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            # Collect fees from this panel state
            all_fees.extend(
                extract_service_fee(soup, keywords=["service fee", "application fee"])
            )

            all_lines.append(f"\n{heading_text.upper()}")

            # Match content panel: same numeric id, no data-tab-btn attribute
            for candidate in soup.find_all("div", id=tab_id):
                if candidate.has_attr("data-tab-btn"):
                    continue  # skip the heading div itself
                for t_copy in candidate.find_all("div", class_="t-copy"):
                    for p in t_copy.find_all("p"):
                        text = p.get_text(" ", strip=True)
                        if text:
                            all_lines.append(f"  {text}")
                    for ul in t_copy.find_all("ul"):
                        for li in ul.find_all("li", recursive=False):
                            text = li.get_text(" ", strip=True)
                            if text:
                                all_lines.append(f"- {text}")

        browser.close()

    text_detail = "\n".join(all_lines).strip()
    service_fee_val = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    data = {
        "state code": "SA",
        "state stream": "Moving_to_South_Australia_from_Overseas",
        "Detail Requirements": text_detail,
        "service fee": service_fee_val,
    }

    return pd.DataFrame([data])


# ── Export ────────────────────────────────────────────────────────────────────


def export_results(df):
    """Export hasil scraping SA ke CSV, JSON, dan formatted XLSX."""
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_sa",
        preview_columns=["state code", "state stream", "service fee"],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Pathway 1: Skilled Employment in South Australia ──────────────────
    df_employment = scrape_sa_pathway(
        stream_name="Skilled_Employment_in_South_Australia",
        url=URL_SA_EMPLOYMENT,
    )

    # ── Pathway 2: South Australian Graduates ─────────────────────────────
    df_graduates = scrape_sa_pathway(
        stream_name="South_Australian_Graduates",
        url=URL_SA_GRADUATES,
    )

    # ── Pathway 3: Outer Regional Skilled Employment ──────────────────────
    df_outer = scrape_sa_pathway(
        stream_name="Outer_Regional_Skilled_Employment",
        url=URL_SA_OUTER,
    )

    # ── Pathway 4: Moving to South Australia from Overseas (tab-click) ────
    df_offshore = scrape_sa_offshore(
        url=URL_SA_OFFSHORE,
    )

    # Gabungkan & export
    final_df = pd.concat(
        [df_employment, df_graduates, df_outer, df_offshore],
        ignore_index=True,
    )
    export_results(final_df)