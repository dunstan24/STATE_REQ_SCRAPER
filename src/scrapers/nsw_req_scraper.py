import logging
import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright


# Path output relatif terhadap lokasi script ini
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "act")

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def extract_service_fee_from_soup(soup):

    fees = []

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True).lower()
        if "service fee" in text:
            found = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)
            if found:
                fees.extend(found)

    return fees

def fetch_and_parse(url, selector="nsw-layout__main"):
    """Fetch HTML dan return BeautifulSoup container (nsw-layout__main)."""
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url, wait_for_selector=selector, extra_wait_seconds=3, bypass_cf=True
    )
    if not html:
        logger.error("Gagal mendapatkan HTML. Cloudflare mungkin memblokir.")
        return None

    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", class_="nsw-layout__main")
    return container
