import logging
import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright

# ==========================
# MASUKKAN LINK DI SINI
# ==========================

URL_GRADUATES = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination"
URL_RESIDENTS = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination/nt-offshore-migration-occupation-list"
URL_OFFSHORE = "PASTE_LINK_HERE"

# ==========================


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "nt")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_service_fee_from_soup(soup):

    fees = []

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True).lower()

        if "service fee" in text or "application fee" in text:
            found = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)

            if found:
                fees.extend(found)

    return fees

def extract_nt_graduate_requirements(soup):
    """Formats the text with bullets and section breaks for better CSV readability."""
    container = soup.find("div", id=lambda x: x and x.startswith("component_"))

    if not container:
        logger.warning("Target component not found")
        return ""

    formatted_texts = []

    # Iterate through tags to apply specific formatting
    for tag in container.find_all(["h2", "h3", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue

        if tag.name in ["h2", "h3"]:
            # Make headers stand out with uppercase and surrounding newlines
            formatted_texts.append(f"\n--- {text.upper()} ---\n")
        
        elif tag.name == "li":
            # Add a visual bullet point
            formatted_texts.append(f"• {text}")
        
        else:
            # Regular paragraphs
            formatted_texts.append(text)

    # Join with newlines; the CSV will preserve these inside the cell
    return "\n".join(formatted_texts).strip()

def extract_nt_resident_requirements(soup):

    container = soup.find("div", id="component_1540902")

    if not container:
        logger.warning("component_1540902 tidak ditemukan")
        return ""

    texts = []

    for tag in container.find_all(["p", "li", "h2", "h3"]):
        text = tag.get_text(" ", strip=True)

        if text:
            texts.append(text)

    return "\n".join(texts)




def get_clean_text(container):
    """General cleaning for non-graduate pages with bullet support."""
    if not container:
        return ""

    lines = []
    for tag in container.find_all(["p", "li", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if not text:
            continue
            
        if tag.name == "li":
            lines.append(f"• {text}")
        elif tag.name in ["h2", "h3"]:
            lines.append(f"\n{text.upper()}\n")
        else:
            lines.append(text)

    return "\n".join(lines).strip()

def fetch_and_parse(url):

    logger.info(f"Fetching: {url}")

    html = get_page_source_playwright(
        url=url,
        wait_for_selector="body",
        extra_wait_seconds=3,
        bypass_cf=True
    )

    if not html:
        logger.error("HTML tidak didapat.")
        return None

    soup = BeautifulSoup(html, "lxml")

    return soup

def scrape_page(name, url):

    soup = fetch_and_parse(url)

    if not soup:
        return "", []

    if name == "NT Graduates":
        text = extract_nt_graduate_requirements(soup)

    elif name == "NT Residents":
        text = extract_nt_resident_requirements(soup)

    else:
        text = get_clean_text(soup)

    fees = extract_service_fee_from_soup(soup)

    logger.info(f"{name} scraped")

    return text, fees


def scrape_nt():

    logger.info("=== Scraping NT Requirements ===")

    # Graduates
    grad_text, grad_fee = scrape_page("NT Graduates", URL_GRADUATES)

    # Residents
    resident_text, resident_fee = scrape_page("NT Residents", URL_RESIDENTS)

    # Offshore
    offshore_text, offshore_fee = scrape_page("NT Offshore", URL_OFFSHORE)

    # Gabungkan semua fee
    all_fees = grad_fee + resident_fee + offshore_fee
    service_fee = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    data = [
        {
            "state code": "NT",
            "state stream": "Graduates",
            "requirements": grad_text,
            "service fee": service_fee,
        },
        {
            "state code": "NT",
            "state stream": "Residents",
            "requirements": resident_text,
            "service fee": service_fee,
        },
        {
            "state code": "NT",
            "state stream": "Offshore",
            "requirements": offshore_text,
            "service fee": service_fee,
        }
    ]

    df = pd.DataFrame(data)

    return df

def export_results(df):

    if df is None or df.empty:
        logger.error("Data kosong.")
        return

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    df.to_csv(
        os.path.join(_OUTPUT_DIR, "requirements_nt.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    df.to_json(
        os.path.join(_OUTPUT_DIR, "requirements_nt.json"),
        orient="records",
        indent=4
    )

    df.to_excel(
        os.path.join(_OUTPUT_DIR, "requirements_nt.xlsx"),
        index=False
    )

    logger.info("Scraping selesai")

    print(df[["state code", "service fee"]])


if __name__ == "__main__":

    final_df = scrape_nt()

    export_results(final_df)