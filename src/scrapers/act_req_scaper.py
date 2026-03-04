""" ACT State Visa Requirements Scraper 

Alur kerja Function:

__main__
  ├── scrape_act_subclass(190, url_general, url_overseas, url_canberra)
  │     ├── fetch_and_parse(url)  ×3            → BeautifulSoup container (col-md-8)
  │     ├── get_clean_text(container)  ×3        → teks terformat dengan hierarki
  │     │     └── format_li(li)                  → format 1 <li>: teks utama + sub-poin (•)
  │     └── extract_service_fee_from_soup(soup)  → list nilai $xxx dari <li> "service fee"
  │
  ├── scrape_act_subclass(491, ...)              → sama seperti di atas untuk subclass 491
  │
  ├── pd.concat([df_190, df_491])                → gabung jadi 1 DataFrame (2 baris)
  │
  └── export_dataframe(final_df, ...)            → CSV + JSON + formatted XLSX
"""


import logging
import os
import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright
from scraper_utils import (
    get_clean_text,
    extract_service_fee,
    export_dataframe,
)

# Output path relative to this script location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "act")

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_service_fee_from_soup(soup):
    """Wrapper untuk extract_service_fee dari scraper_utils."""
    return extract_service_fee(soup)


def fetch_and_parse(url, selector="#main.col-md-8"):
    """Fetch HTML dan return BeautifulSoup container (col-md-8)."""
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url, wait_for_selector=selector, extra_wait_seconds=3, bypass_cf=True
    )
    if not html:
        logger.error("Gagal mendapatkan HTML. Cloudflare mungkin memblokir.")
        return None

    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", {"id": "main", "class": "col-md-8"})
    if not container:
        container = soup.find("div", class_="col-md-8")
    return container




def scrape_act_subclass(subclass, url_general, url_overseas, url_canberra):
    """Scrape ACT nomination criteria untuk subclass tertentu."""
    logger.info(f"=== Scraping ACT Subclass {subclass} ===")

    soup_general = fetch_and_parse(url_general)
    soup_overseas = fetch_and_parse(url_overseas)
    soup_canberra = fetch_and_parse(url_canberra)

    text_general = get_clean_text(soup_general)
    text_overseas = get_clean_text(soup_overseas)
    text_canberra = get_clean_text(soup_canberra)

    # Extract Service Fee from each page with page name label
    pages = [
        ("overseas", soup_overseas),
        ("canberra", soup_canberra),
        ("general", soup_general),
    ]

    service_fees = []
    for name, soup in pages:
        if soup:
            fees = extract_service_fee_from_soup(soup)
            if fees:
                for fee in fees:
                    service_fees.append(f"{fee} ({name})")

    if service_fees:
        service_fee_value = ", ".join(service_fees)
    else:
        service_fee_value = "-"

    data = {
        "state code": "ACT",
        "state stream": str(subclass),
        "General Requirements": text_general,
        "Requirements Canberra Residents": text_canberra,
        "Requirements overseas": text_overseas,
        "service fee": service_fee_value,
    }

    return pd.DataFrame([data])


def export_results(df):
    """Export hasil scraping ACT ke CSV, JSON, dan formatted XLSX."""
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_act",
        preview_columns=["state code", "state stream", "service fee"],
    )


if __name__ == "__main__":
    # Baris 1: Subclass 190
    df_190 = scrape_act_subclass(
        subclass=190,
        url_general="https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria",
        url_overseas="https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/overseas-applicant-eligibility",
        url_canberra="https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/canberra-resident-applicant-eligibility",
    )

    # Baris 2: Subclass 491
    df_491 = scrape_act_subclass(
        subclass=491,
        url_general="https://www.act.gov.au/migration/skilled-migrants/491-nomination-criteria",
        url_overseas="https://www.act.gov.au/migration/skilled-migrants/491-nomination-criteria/491-nomination-overseas-applicant-eligibility",
        url_canberra="https://www.act.gov.au/migration/skilled-migrants/491-nomination-criteria/491-nomination-canberra-resident-applicant-eligibility",
    )

    # Combine into a single DataFrame
    final_df = pd.concat([df_190, df_491], ignore_index=True)

    export_results(final_df)
