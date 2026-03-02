import logging
import re
import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_service_fee(text):
    """Mencari pola angka dengan simbol $ di depannya"""
    # Mencari pola seperti $300, $1,200, dsb.
    fees = re.findall(r"\$\d+(?:,\d+)?", text)
    return list(set(fees))  # Kembalikan nilai unik


def get_clean_text_from_url(url, selector="#main.col-md-8"):
    """Helper untuk ambil HTML dan ekstrak semua teks LI menjadi satu string"""
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url, wait_for_selector=selector, extra_wait_seconds=3, bypass_cf=True
    )
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", {"id": "main", "class": "col-md-8"})
    if not container:
        # Fallback jika ID main tidak spesifik di halaman tersebut
        container = soup.find("div", class_="col-md-8")

    if container:
        # Ambil semua teks dari LI
        lines = [
            li.get_text(strip=True)
            for li in container.find_all("li")
            if li.get_text(strip=True)
        ]
        return "\n".join(lines)
    return ""


def scrape_act_all_streams():
    # URL Targets
    url_overseas = "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/overseas-applicant-eligibility"
    url_canberra = "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/canberra-resident-applicant-eligibility"
    url_general = (
        "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria"
    )

    # 1. Scrape masing-masing halaman
    text_overseas = get_clean_text_from_url(url_overseas)
    text_canberra = get_clean_text_from_url(url_canberra)
    text_general = get_clean_text_from_url(url_general)

    # 2. Gabungkan General ke masing-masing (opsional, tapi biasanya General berlaku untuk keduanya)
    # Jika ingin dipisah, biarkan saja. Di sini saya biarkan murni dari halamannya.

    # 3. Ekstrak Service Fee dari semua teks yang didapat
    combined_all_text = text_overseas + " " + text_canberra + " " + text_general
    found_fees = extract_service_fee(combined_all_text)

    # Logika Service Fee: jika unik ambil satu, jika beda beri koma
    service_fee_value = ", ".join(found_fees) if found_fees else "-"

    # 4. Susun ke dalam Dictionary untuk DataFrame
    data = {
        "state code": "ACT",
        "state stream": "190",
        "Requirements Canberra Residents": text_canberra,
        "Requirements overseas": text_overseas,
        "General Requirements": text_general,
        "service fee": service_fee_value,
    }

    return pd.DataFrame([data])


def export_results(df):
    if df is not None and not df.empty:
        df.to_csv("act_unified_190.csv", index=False, encoding="utf-8-sig")
        df.to_json("act_unified_190.json", orient="records", indent=4)
        logger.info("Scraping selesai. Data disimpan ke act_unified_190.csv")
        print("\n--- Preview DataFrame ---")
        print(df[["state code", "state stream", "service fee"]])
    else:
        logger.error("Dataframe kosong.")


if __name__ == "__main__":
    final_df = scrape_act_all_streams()
    export_results(final_df)
