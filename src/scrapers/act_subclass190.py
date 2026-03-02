import logging
import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def scrape_act_content():
    url = "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/overseas-applicant-eligibility"

    # Memanggil helper Anda
    # Selector diperingkas untuk menunggu id main muncul
    html = get_page_source_playwright(
        url=url,
        wait_for_selector="#main.col-md-8",
        extra_wait_seconds=5,
        bypass_cf=True,
    )

    if not html:
        logger.error("Gagal mendapatkan HTML. Cloudflare mungkin memblokir.")
        return None

    soup = BeautifulSoup(html, "lxml")

    # Mencari spesifik id="main" DAN class="col-md-8"
    main_content = soup.find("div", {"id": "main", "class": "col-md-8"})

    if not main_content:
        logger.warning("Elemen id='main' dengan class='col-md-8' tidak ditemukan.")
        return None

    extracted_data = []

    # Strategi: Mengambil Heading (h2/h3) dan List Item (li) di bawahnya
    # Agar data di CSV lebih informatif (tahu konteks list tersebut)
    all_li_texts = [
        li.get_text(strip=True)
        for li in main_content.find_all("li")
        if li.get_text(strip=True)
    ]

    # Gabungkan semua list menjadi satu string panjang
    combined_text = "\n".join(all_li_texts)

    # Buat DataFrame dengan satu baris dan satu kolom
    df = pd.DataFrame([{"requirement overseas": combined_text}])
    return df
    # current_section = "General"

    # # Cari semua elemen penting di dalam kontainer utama
    # elements = main_content.find_all(["h2", "h3", "li"])

    # for el in elements:
    #     text = el.get_text(strip=True)
    #     if not text:
    #         continue

    #     if el.name in ["h2", "h3"]:
    #         current_section = text  # Update nama kategori saat ketemu judul baru
    #     elif el.name == "li":
    #         extracted_data.append(
    #             {"Section": current_section, "Requirement": text, "Source": url}
    #         )

    # return pd.DataFrame(extracted_data)


def export_data(df):
    if df is not None and not df.empty:
        # Export ke CSV (Bisa dibuka di Excel)
        df.to_csv("act_migration_criteria.csv", index=False, encoding="utf-8-sig")
        # Export ke JSON
        df.to_json("act_migration_criteria.json", orient="records", indent=4)

        logger.info(f"Berhasil menyimpan {len(df)} baris data.")
        print("\n--- Preview 5 Data Teratas ---")
        print(df.head())
    else:
        logger.error("Tidak ada data untuk diekspor.")


if __name__ == "__main__":
    df_result = scrape_act_content()
    export_data(df_result)
