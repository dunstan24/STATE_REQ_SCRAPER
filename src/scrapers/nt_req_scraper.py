import logging
import os
import re
import pandas as pd
from bs4 import BeautifulSoup
# Pastikan playwright_helper tersedia di environment Anda
# from playwright_helper import get_page_source_playwright 

# ==========================
# LINK SESUAI GAMBAR
# ==========================
URL_NT = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination"
URL_OFFSHORE = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination/nt-offshore-migration-occupation-list"

# ==========================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "nt")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
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

def get_clean_text(soup):
    """Fungsi umum untuk ekstraksi konten requirements"""
    container = soup.find("div", id=lambda x: x and x.startswith("component_"))
    if not container:
        container = soup.find("body") 

    lines = []
    for tag in container.find_all(["p", "li", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if not text: continue
            
        if tag.name == "li":
            lines.append(f"• {text}")
        elif tag.name in ["h2", "h3"]:
            lines.append(f"\n{text.upper()}\n")
        else:
            lines.append(text)

    return "\n".join(lines).strip()

def fetch_and_parse(url):
    logger.info(f"Fetching: {url}")
    try:
        from playwright_helper import get_page_source_playwright
        html = get_page_source_playwright(url=url, wait_for_selector="body", extra_wait_seconds=3, bypass_cf=True)
    except ImportError:
        logger.error("playwright_helper tidak ditemukan.")
        return None

    if not html:
        logger.error("HTML tidak didapat.")
        return None
    return BeautifulSoup(html, "lxml")

def scrape_page(url):
    soup = fetch_and_parse(url)
    if not soup:
        return "", []
    
    text = get_clean_text(soup)
    fees = extract_service_fee_from_soup(soup)
    return text, fees

def scrape_nt():
    logger.info("=== Scraping NT Requirements ===")

    # 1. Scraping Northern Territory (Main/Graduates)
    nt_text, nt_fees = scrape_page(URL_NT)

    # 2. Scraping Offshore
    offshore_text, offshore_fees = scrape_page(URL_OFFSHORE)

    # Gabungkan fee
    all_fees = nt_fees + offshore_fees
    service_fee_val = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    # Format data persis seperti screenshot
    data = [
        {
            "state code": "NT",
            "state stream": "Northen_Territory",
            "requirements": nt_text,
            "service fee": service_fee_val,
        },
        {
            "state code": "NT",
            "state stream": "Northen_Territory_Offshore",
            "requirements": offshore_text,
            "service fee": service_fee_val,
        }
    ]

    return pd.DataFrame(data)

def export_results(df):
    if df is None or df.empty:
        logger.error("Data kosong.")
        return

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    
    # --- EXPORT JSON ---
    json_path = os.path.join(_OUTPUT_DIR, "requirements_nt.json")
    df.to_json(json_path, orient="records", indent=4, force_ascii=False)
    
    # --- EXPORT CSV & EXCEL (Opsional, agar tetap lengkap) ---
    df.to_csv(os.path.join(_OUTPUT_DIR, "requirements_nt.csv"), index=False, encoding="utf-8-sig")
    df.to_excel(os.path.join(_OUTPUT_DIR, "requirements_nt.xlsx"), index=False)

    logger.info(f"Scraping selesai. File JSON disimpan di: {json_path}")
    print("\nPreview Data:")
    print(df[["state code", "state stream", "service fee"]])

if __name__ == "__main__":
    final_df = scrape_nt()
    export_results(final_df)