"""
State Visa Requirements Scraper — Wide Format Output

Alur kerja:

__main__
  ├── untuk setiap pathway (tse, tsg, ter, tbo):
  │     ├── fetch_and_click_accordions(url)
  │     │     └── Playwright: klik semua accordion button → return HTML lengkap
  │     ├── parse_subclass_section(soup, subclass=190)
  │     └── parse_subclass_section(soup, subclass=491)
  │
  ├── build_wide_dataframe(all_pathway_data)
  │     → baris: [190, 491]
  │     → kolom: state_code, state_stream, tse, tsg, ter, tbo
  │
  └── export_dataframe(df)

Struktur accordion per halaman:
  Tiap subclass diidentifikasi dari heading (h2) yang mengandung "190" / "491"
  lalu accordion div#content-accordion di bawahnya berisi:
    ├── dropdown 0: Minimum Requirements
    ├── dropdown 1: Priority Attributes
    └── dropdown 2: Required Documents
"""

import logging
import os
import pandas as pd
from bs4 import BeautifulSoup
from general_tools_scrap import get_clean_text, export_dataframe

# ── Output path ───────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "tas")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Pathway URL config ────────────────────────────────────────────────────────
PATHWAY_URLS = {
    "tse": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-skilled-employment-pathways-tse",
    "tsg": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-skilled-graduate-pathways-tsg",
    "ter": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-established-resident-pathways-ter",
    "tbo": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-business-operator-pathway-tbo",
}

# Nama dropdown yang di-extract (urutan harus sesuai urutan di halaman)
DROPDOWN_KEYS = ["minimum_requirements", "priority_attributes", "required_documents"]

# Subclass yang di-extract
SUBCLASSES = [190, 491]


# ── Step 1: Fetch halaman ─────────────────────────────────────────────────────


def fetch_and_click_accordions(url: str) -> BeautifulSoup | None:
    """
    Fetch halaman lalu klik semua accordion button yang masih collapsed secara manual.
    Digunakan untuk halaman seperti TBO yang accordion-nya tidak auto-expand.

    Masalah khusus TBO: ada atribut data-bs-parent="#content-accordion" yang
    menyebabkan Bootstrap menutup item lain saat satu item dibuka (mode eksklusif).
    Solusi: hapus data-bs-parent via JS sebelum klik agar semua item bisa terbuka
    bersamaan.
    """
    from playwright.sync_api import sync_playwright

    logger.info(f"Fetching + manual click accordions: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Hapus data-bs-parent agar semua accordion bisa terbuka bersamaan
            page.evaluate("""
                document.querySelectorAll('#content-accordion [data-bs-parent]')
                    .forEach(el => el.removeAttribute('data-bs-parent'));
            """)

            # Klik semua button accordion yang masih collapsed
            buttons = page.query_selector_all(
                "#content-accordion button.accordion-button"
            )
            logger.info(f"  Ditemukan {len(buttons)} accordion button")

            for btn in buttons:
                try:
                    if btn.get_attribute("aria-expanded") == "false":
                        btn.click()
                        page.wait_for_timeout(500)
                except Exception as e:
                    logger.warning(f"  Gagal klik button: {e}")

            page.wait_for_timeout(1000)
            html = page.content()
            browser.close()

        return BeautifulSoup(html, "lxml")

    except Exception as e:
        logger.error(f"Gagal fetch {url}: {e}")
        return None


# ── Step 2: Parser — unified untuk semua pathway ─────────────────────────────


def _find_accordion_for_subclass(soup: BeautifulSoup, subclass: int):
    """
    Cari accordion (div#content-accordion) yang sesuai dengan subclass.

    Strategi dua tahap:
    1. Cari heading (h2/h3) di luar accordion yang mengandung angka subclass,
       lalu ambil div#content-accordion pertama setelah heading tersebut.
       (untuk TSE, TSG, TER)
    2. Fallback: cari accordion yang accordion-button-nya mengandung angka subclass.
       (untuk TBO yang tidak punya heading di luar accordion)

    Jika tidak ditemukan, return None.
    """
    subclass_str = str(subclass)

    # ── Tahap 1: cari heading di luar accordion ──────────────────────────
    headings = soup.find_all(["h2", "h3"])
    for heading in headings:
        # Skip heading yang ada di dalam accordion (misal accordion-header)
        if heading.find_parent("div", id="content-accordion"):
            continue
        heading_text = heading.get_text(" ", strip=True)
        if subclass_str in heading_text:
            sibling = heading.find_next(
                "div", {"class": "accordion", "id": "content-accordion"}
            )
            if sibling:
                logger.info(
                    f"  Heading ditemukan: '{heading_text}' → accordion di bawahnya"
                )
                return sibling

    # ── Tahap 2: fallback — cek accordion-button di dalam accordion ──────
    accordions = soup.find_all("div", {"id": "content-accordion"})
    for accordion in accordions:
        buttons = accordion.find_all("button", class_="accordion-button")
        for btn in buttons:
            btn_text = btn.get_text(" ", strip=True)
            if subclass_str in btn_text:
                logger.info(
                    f"  Accordion-button ditemukan: '{btn_text}' → gunakan accordion ini"
                )
                return accordion

    logger.info(f"  Tidak ada heading/accordion untuk subclass {subclass} di halaman ini")
    return None


def parse_subclass_section(soup: BeautifulSoup, subclass: int) -> dict:
    """
    Extract data dari accordion yang sesuai dengan subclass.

    Menggunakan heading (h2/h3) untuk mengidentifikasi accordion mana
    yang berisi data subclass 190 atau 491.
    Ini bekerja untuk semua pathway:
    - TSE, TSG, TER: 2 accordion (190 + 491)
    - TBO: 1 accordion (hanya 491)
    """
    result = {key: "-" for key in DROPDOWN_KEYS}

    target_accordion = _find_accordion_for_subclass(soup, subclass)
    if not target_accordion:
        return result

    items = target_accordion.find_all("div", class_="accordion-item")
    logger.info(f"  Subclass {subclass} → {len(items)} accordion-item ditemukan")

    for i, item in enumerate(items):
        if i >= len(DROPDOWN_KEYS):
            break
        body = item.find("div", class_="accordion-body")
        if not body:
            logger.warning(f"  Dropdown[{i}] tidak punya accordion-body")
            continue
        text = get_clean_text(body)
        result[DROPDOWN_KEYS[i]] = text if text else "-"

    return result


# ── Step 3: Scrape semua pathway → kumpulkan data ────────────────────────────


def scrape_all_pathways(pathway_urls: dict) -> dict:
    """
    Untuk setiap pathway URL, scrape data subclass 190 dan 491.
    Ketiga field digabung menjadi 1 teks per pathway.

    Semua pathway menggunakan parser yang sama (parse_subclass_section).
    Parser mencari heading (h2) yang mengandung "190" / "491" untuk
    mengidentifikasi accordion yang sesuai. Jika subclass tidak ditemukan
    di halaman (misal TBO hanya punya 491), otomatis diisi '-'.

    Returns:
    {
        190: { "tse": "...", "tsg": "...", "ter": "...", "tbo": "-" },
        491: { "tse": "...", "tsg": "...", "ter": "...", "tbo": "..." }
    }
    """
    all_data = {sc: {} for sc in SUBCLASSES}
    labels = {
        "minimum_requirements": "Minimum Requirements",
        "priority_attributes": "Priority Attributes",
        "required_documents": "Required Documents",
    }

    def combine_fields(section_data: dict) -> str:
        parts = [f"[{labels[k]}]\n{section_data.get(k, '-')}" for k in DROPDOWN_KEYS]
        return "\n\n".join(parts)

    for pathway_name, url in pathway_urls.items():
        logger.info(f"\n=== Pathway: {pathway_name.upper()} ===")
        soup = fetch_and_click_accordions(url)

        if not soup:
            logger.error(f"  Skip pathway {pathway_name} — gagal fetch")
            for sc in SUBCLASSES:
                all_data[sc][pathway_name] = "-"
            continue

        for subclass in SUBCLASSES:
            logger.info(f"  Parsing subclass {subclass}...")
            section_data = parse_subclass_section(soup, subclass=subclass)
            combined = combine_fields(section_data)
            # Jika semua field '-', set pathway ke '-'
            if all(v == "-" for v in section_data.values()):
                all_data[subclass][pathway_name] = "-"
            else:
                all_data[subclass][pathway_name] = combined

    return all_data


# ── Step 4: Build DataFrame ───────────────────────────────────────────────────


def build_wide_dataframe(all_data: dict) -> pd.DataFrame:
    """
    Ubah all_data menjadi DataFrame wide format:

    state_code | state_stream | tse  | tsg  | ter  | tbo
    TSA        | 190          | ...  | ...  | ...  | ...
    TSA        | 491          | ...  | ...  | ...  | ...
    """
    rows = []
    for subclass in SUBCLASSES:
        row = {"state_code": "TSA", "state_stream": subclass}
        row.update(all_data[subclass])  # langsung: tse, tsg, ter, tsb
        rows.append(row)

    df = pd.DataFrame(rows)

    # Urutkan kolom: state_code & state_stream dulu, lalu tiap pathway
    ordered_cols = ["state_code", "state_stream"] + list(PATHWAY_URLS.keys())
    ordered_cols = [c for c in ordered_cols if c in df.columns]
    df = df[ordered_cols]

    return df


# ── Step 5: Export ────────────────────────────────────────────────────────────


def export_results(df: pd.DataFrame):
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_tas",
        preview_columns=["state_code", "state_stream"],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Mulai scraping state visa requirements...")

    all_data = scrape_all_pathways(PATHWAY_URLS)
    df = build_wide_dataframe(all_data)

    logger.info(f"\nDataFrame shape: {df.shape}")
    logger.info(f"Kolom: {list(df.columns)}")
    logger.info(f"\nPreview:\n{df[['state_code', 'state_stream']].to_string()}")

    export_results(df)
    logger.info("Selesai!")
