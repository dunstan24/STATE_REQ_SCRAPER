""" VIC State Visa Requirements Scraper

Alur kerja Function:

__main__
  ├── scrape_vic_subclass("Skilled_Nominated_Visa_Subclass_190", URL_VIC_190)
  │     ├── _scrape_accordion_page(url)    → teks requirements (Playwright accordion click)
  │     └── extract_service_fee(soup)      → list nilai $xxx
  │
  ├── scrape_vic_subclass("Skilled_Work_Regional_Visa_Subclass_491", URL_VIC_491)
  │
  ├── pd.concat([df_190, df_491])          → gabung jadi 1 DataFrame (2 baris)
  │
  └── export_dataframe(final_df, ...)      → CSV + JSON + formatted XLSX
"""

import logging
import os

import pandas as pd
from bs4 import BeautifulSoup
from general_tools_scrap import (
    get_clean_text,
    extract_service_fee,
    export_dataframe,
)


# ==========================
# LINK VIC
# ==========================
URL_VIC_190 = "https://liveinmelbourne.vic.gov.au/migrate/skilled-migration-visas/skilled-nominated-visa-subclass-190"
URL_VIC_491 = "https://liveinmelbourne.vic.gov.au/migrate/skilled-migration-visas/491"
# ==========================

# Output path relative to this script location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "vic")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ── Parsing Helpers ───────────────────────────────────────────────────────────


def _extract_accordion_body(body):
    """Ekstrak teks dari satu accordion__body element.

    Memproses h2-h5, p, dan ul secara berurutan sesuai DOM order.

    Parameters
    ----------
    body : BeautifulSoup element — accordion body element

    Returns
    -------
    list[str] — baris-baris teks dari body
    """
    lines = []
    for el in body.find_all(["h2", "h3", "h4", "h5", "p", "ul"]):
        tag = el.name

        if tag in ("h2", "h3", "h4", "h5"):
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(f"  [{text}]")

        elif tag == "p":
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(f"  {text}")

        elif tag == "ul":
            for li in el.find_all("li", recursive=False):
                text = li.get_text(" ", strip=True)
                if text:
                    lines.append(f"- {text}")

    return lines


def _scrape_accordion_page(url):
    """Scrape halaman VIC yang menggunakan accordion structure via Playwright.

    Setiap accordion item memiliki:
      - Heading : element dengan class mengandung 'accordion__header'
      - Content : element dengan class mengandung 'accordion__body'

    Flow per accordion item:
      1. Klik header untuk expand
      2. Tunggu animasi CSS
      3. Snapshot DOM
      4. Ekstrak body content dengan index yang sama
      5. Ulangi untuk header berikutnya

    Parameters
    ----------
    url : str — URL halaman VIC

    Returns
    -------
    tuple[str, list[str]] — (teks requirements, list fee values)
    """
    logger.info(f"Fetching (accordion click mode): {url}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright tidak terinstall.")
        return "", []

    all_lines = []
    all_fees = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # Count total accordion headers upfront
        total = page.eval_on_selector_all(
            "[class*='accordion__header']",
            "els => els.length",
        )
        logger.info(f"Found {total} accordion headers")

        for i in range(total):
            # Re-query headers each iteration (DOM may shift after click)
            headers = page.query_selector_all("[class*='accordion__header']")
            if i >= len(headers):
                logger.warning(f"Header index {i} out of range, skipping")
                break

            header = headers[i]

            # 1. Get heading text BEFORE clicking
            heading_text = header.inner_text().strip()
            if not heading_text:
                continue

            logger.info(f"Clicking accordion [{i}]: {heading_text}")

            # 2. Click to expand
            header.click()
            page.wait_for_timeout(600)  # wait for CSS expand animation

            # 3. Snapshot DOM after this click
            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            # Collect fees from this snapshot
            all_fees.extend(
                extract_service_fee(soup, keywords=["service fee", "application fee"])
            )

            all_lines.append(f"\n{heading_text.upper()}")

            # 4. Find the Nth accordion__body (same index as header)
            bodies = soup.find_all(
                lambda tag: tag.get("class")
                and any("accordion__body" in c for c in tag.get("class", []))
            )

            if i < len(bodies):
                body_lines = _extract_accordion_body(bodies[i])
                all_lines.extend(body_lines)
            else:
                logger.warning(
                    f"No accordion__body at index {i} for: {heading_text}"
                )

        browser.close()

    return "\n".join(all_lines).strip(), list(set(all_fees))


# ── Scraper Utama ─────────────────────────────────────────────────────────────


def scrape_vic_subclass(stream_name, url):
    """Scrape VIC visa requirements untuk satu subclass.

    Parameters
    ----------
    stream_name : str — nama stream (misal: "Skilled_Nominated_Visa_Subclass_190")
    url         : str — URL halaman VIC

    Returns
    -------
    pd.DataFrame — 1 baris dengan kolom:
        state code, state stream, requirements, service fee
    """
    logger.info(f"=== Scraping VIC: {stream_name} ===")

    text_req, fees = _scrape_accordion_page(url)
    service_fee_val = ", ".join(sorted(set(fees))) if fees else "-"

    data = {
        "state code": "VIC",
        "state stream": stream_name,
        "requirements": text_req,
        "service fee": service_fee_val,
    }

    return pd.DataFrame([data])


def scrape_vic():
    """Scrape semua VIC requirements dan return combined DataFrame."""
    df_190 = scrape_vic_subclass("Subclass_190", URL_VIC_190)
    df_491 = scrape_vic_subclass("Subclass_491", URL_VIC_491)
    return pd.concat([df_190, df_491], ignore_index=True)


# ── Export ────────────────────────────────────────────────----------------------------------------------------------------


def export_results(df):
    """Export hasil scraping VIC ke CSV, JSON, dan formatted XLSX."""
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_vic",
        preview_columns=["state code", "state stream", "service fee"],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Subclass 190: Skilled Nominated Visa ──────────────────────────────
    df_190 = scrape_vic_subclass(
        stream_name="Subclass_190",
        url=URL_VIC_190,
    )

    # ── Subclass 491: Skilled Work Regional Visa ──────────────────────────
    df_491 = scrape_vic_subclass(
        stream_name="Subclass_491",
        url=URL_VIC_491,
    )

    # Gabungkan & export
    final_df = pd.concat([df_190, df_491], ignore_index=True)
    export_results(final_df)