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
    """Cari <li> yang punya <strong> berisi 'Service fee', lalu ambil nilai $xxx dari li itu."""
    for li in soup.find_all("li"):
        strong = li.find("strong")
        if strong and "service fee" in strong.get_text(strip=True).lower():
            li_text = li.get_text(strip=True)
            fees = re.findall(r"\$[\d,]+(?:\.\d{2})?", li_text)
            if fees:
                return ", ".join(fees)
    return "-"


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


def get_clean_text(container):
    """Ekstrak teks dari container. Prioritas: <li>, lalu elemen lain, lalu teks mentah."""
    if not container:
        return ""

    # Coba ambil teks dari LI dulu
    lines = [
        li.get_text(strip=True)
        for li in container.find_all("li")
        if li.get_text(strip=True)
    ]
    if lines:
        return "\n".join(lines)

    # Fallback: jika tidak ada <li> (seperti halaman general),
    # ambil semua konten teks dari elemen h2, h3, p, div, span, dll.
    all_text = []
    for el in container.find_all(["h2", "h3", "h4", "p", "span", "div", "a"]):
        text = el.get_text(strip=True)
        if text and text not in all_text:
            all_text.append(text)
    if all_text:
        return "\n".join(all_text)

    # Fallback terakhir: ambil semua teks mentah dari container
    return container.get_text(separator="\n", strip=True)


def scrape_act_subclass(subclass, url_general, url_overseas, url_canberra):
    """Scrape ACT nomination criteria untuk subclass tertentu."""
    logger.info(f"=== Scraping ACT Subclass {subclass} ===")

    soup_general = fetch_and_parse(url_general)
    soup_overseas = fetch_and_parse(url_overseas)
    soup_canberra = fetch_and_parse(url_canberra)

    text_general = get_clean_text(soup_general)
    text_overseas = get_clean_text(soup_overseas)
    text_canberra = get_clean_text(soup_canberra)

    service_fee_value = "-"
    for soup in [soup_overseas, soup_canberra, soup_general]:
        if soup:
            fee = extract_service_fee_from_soup(soup)
            if fee != "-":
                service_fee_value = fee
                break

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
    if df is not None and not df.empty:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)

        df.to_csv(
            os.path.join(_OUTPUT_DIR, "requirements_act.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        df.to_json(
            os.path.join(_OUTPUT_DIR, "requirements_act.json"),
            orient="records",
            indent=4,
        )
        df.to_excel(
            os.path.join(_OUTPUT_DIR, "requirements_act.xlsx"),
            index=False,
        )
        logger.info(f"Scraping selesai. Data disimpan ke {_OUTPUT_DIR}")
        print("\n--- Preview DataFrame ---")
        print(df[["state code", "state stream", "service fee"]])
    else:
        logger.error("Dataframe kosong.")


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

    # Gabungkan jadi satu DataFrame
    final_df = pd.concat([df_190, df_491], ignore_index=True)

    export_results(final_df)
