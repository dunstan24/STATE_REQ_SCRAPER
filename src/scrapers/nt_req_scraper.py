""" NT State Visa Requirements Scraper

Alur kerja Function:

__main__
  ├── scrape_nt()
  │     ├── scrape_page(URL_NT)          → (text, fees)
  │     │     ├── fetch_and_parse(url)   → BeautifulSoup <article> container
  │     │     ├── get_clean_text_nt()    → h2/h3 as headings, p as paragraphs, li as bullets
  │     │     └── extract_service_fee()  → list nilai $xxx
  │     ├── scrape_page(URL_OFFSHORE)    → (text, fees)
  │     └── pd.DataFrame(data)           → 2 baris (NT + NT Offshore)
  │
  └── export_results(df)                 → CSV + JSON + formatted XLSX
"""

import logging
import os
import pandas as pd
from bs4 import BeautifulSoup, Tag
from playwright_helper import get_page_source_playwright
from general_tools_scrap import (
    extract_service_fee,
    export_dataframe,
)

# ==========================
# URLs
# ==========================
URL_NT       = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination"
URL_OFFSHORE = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination/nt-offshore-migration-occupation-list"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "nt")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_service_fee_from_soup(soup):
    """Wrapper untuk extract_service_fee dari general_tools_scrap."""
    return extract_service_fee(soup, keywords=["service fee", "application fee"])


def get_clean_text_nt(article):
    """
    Format teks dari <article> NT dengan hierarki:
      - <h2>  → HEADING (uppercase, blank line before/after)
      - <h3>  → Subheading (blank line before/after)
      - <p>   → paragraph text
      - <ul>/<ol> → bullet points (• item)
      - nested <ul> inside <li> → indented sub-bullets (  • item)
    """
    if not article:
        return ""

    lines = []

    def process_node(node, indent=0):
        if not isinstance(node, Tag):
            return

        if node.name in ["h2"]:
            text = node.get_text(" ", strip=True)
            if text:
                lines.append("")
                lines.append(text.upper())
                lines.append("")

        elif node.name in ["h3"]:
            text = node.get_text(" ", strip=True)
            if text:
                lines.append("")
                lines.append(text)
                lines.append("")

        elif node.name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                lines.append(text)

        elif node.name in ["ul", "ol"]:
            for li in node.find_all("li", recursive=False):
                # Get direct text of <li> (exclude nested ul/ol)
                direct_text = " ".join(
                    child.get_text(" ", strip=True) if isinstance(child, Tag) and child.name not in ["ul", "ol"]
                    else (child.strip() if not isinstance(child, Tag) else "")
                    for child in li.children
                ).strip()

                prefix = "  " * indent + "\u2022  "
                if direct_text:
                    lines.append(f"{prefix}{direct_text}")

                # Handle nested lists
                for nested in li.find_all(["ul", "ol"], recursive=False):
                    for sub_li in nested.find_all("li", recursive=False):
                        sub_text = sub_li.get_text(" ", strip=True)
                        if sub_text:
                            lines.append(f"  {prefix}{sub_text}")

        elif node.name == "article":
            # Recurse into nested <article> tags
            for child in node.children:
                process_node(child, indent)

    for child in article.children:
        process_node(child)

    # Clean up: remove consecutive blank lines
    result = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    return "\n".join(result).strip()


def fetch_and_parse(url):
    """Fetch HTML dan return BeautifulSoup <article> element."""
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url,
        wait_for_selector="div[id^='component_'] article",
        extra_wait_seconds=3,
        bypass_cf=False
    )

    if not html:
        logger.error(f"Gagal mendapatkan HTML dari: {url}")
        return None

    soup = BeautifulSoup(html, "lxml")

    # Find the component_ div first, then get the top-level <article> inside it
    component = soup.find("div", id=lambda x: x and x.startswith("component_"))
    if not component:
        logger.warning(f"Container 'component_*' tidak ditemukan di: {url}")
        return None

    article = component.find("article")
    if not article:
        logger.warning(f"<article> tidak ditemukan di dalam component_ div: {url}")
        return None

    return article


def scrape_page(url):
    """Fetch satu halaman dan return (clean_text, service_fees)."""
    article = fetch_and_parse(url)
    if not article:
        return "", []

    text = get_clean_text_nt(article)
    fees = extract_service_fee_from_soup(article)
    return text, fees


def scrape_nt():
    """Scrape NT nomination requirements dari semua halaman."""
    logger.info("=== Scraping NT Requirements ===")

    nt_text,       nt_fees       = scrape_page(URL_NT)
    offshore_text, offshore_fees = scrape_page(URL_OFFSHORE)

    all_fees = nt_fees + offshore_fees
    service_fee_val = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    data = [
        {
            "state code":   "NT",
            "state stream": "Northern_Territory",
            "requirements": nt_text,
            "service fee":  service_fee_val,
        },
        {
            "state code":   "NT",
            "state stream": "Northern_Territory_Offshore",
            "requirements": offshore_text,
            "service fee":  service_fee_val,
        },
    ]

    return pd.DataFrame(data)


def export_results(df):
    """Export hasil scraping NT ke CSV, JSON, dan formatted XLSX."""
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_nt",
        preview_columns=["state code", "state stream", "service fee"],
    )


if __name__ == "__main__":
    final_df = scrape_nt()
    export_results(final_df)