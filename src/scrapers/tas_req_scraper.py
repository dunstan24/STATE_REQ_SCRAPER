"""
State Visa Requirements Scraper — Wide Format Output

Alur kerja:

__main__
  ├── untuk setiap pathway (tse, tsg, ter, tbo):
  │     ├── fetch_and_expand_accordions(url)
  │     │     └── Playwright: klik semua accordion button → return HTML lengkap
  │     ├── parse_subclass_section(soup, index=0) → dict untuk subclass 190
  │     └── parse_subclass_section(soup, index=1) → dict untuk subclass 491
  │
  ├── build_wide_dataframe(all_pathway_data)
  │     → baris: [190, 491]
  │     → kolom: state_code, state_stream, tse, tsg, ter, tbo
  │
  └── export_dataframe(df)

Struktur accordion per halaman:
  accordion[0] → subclass 190
    ├── dropdown 0: Minimum Requirements
    ├── dropdown 1: Priority Attributes
    └── dropdown 2: Required Documents
  accordion[1] → subclass 491
    └── (sama)
"""

import logging
import os
import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright
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
    "tse": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-skilled-employment-pathways-tse",  # ganti URL asli
    "tsg": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-skilled-graduate-pathways-tsg",
    "ter": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-established-resident-pathways-ter",
    "tbo": "https://www.migration.tas.gov.au/skilled_migration/skilled-workers-and-graduates-living-in-Tasmania/tasmanian-business-operator-pathways-tbo",
}
PATHWAY_SUBCLASS_INDEX = {
    "tse": {190: 0, 491: 1},
    "tsg": {190: 0, 491: 1},
    "ter": {190: 0, 491: 1},
    "tbo": {190: None, 491: 0},  # 190 tidak ada, 491 ada di index 0
}   

# Nama dropdown yang di-extract (urutan harus sesuai urutan di halaman)
DROPDOWN_KEYS = ["minimum_requirements", "priority_attributes", "required_documents"]

# Subclass yang di-extract (urutan accordion di halaman)
SUBCLASSES = [190, 491]


# ── Step 1: Fetch + klik semua accordion ─────────────────────────────────────


def fetch_and_expand_accordions(url: str) -> BeautifulSoup | None:
    """
    Fetch halaman via playwright_helper, lalu parse dengan BeautifulSoup.
    Konten accordion sudah di-expand oleh Playwright sebelum HTML di-return.
    """
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url,
        wait_for_selector="body",
        extra_wait_seconds=3,
        bypass_cf=False,
    )
    if not html:
        logger.error(f"Gagal mendapatkan HTML dari: {url}")
        return None

    return BeautifulSoup(html, "lxml")


# ── Step 2: Extract section per subclass ─────────────────────────────────────


def parse_subclass_section(soup: BeautifulSoup, subclass_index: int) -> dict:
    """
    Ambil accordion ke-N (0=190, 1=491) dan extract tiap dropdown di dalamnya.

    Returns dict:
    {
        "minimum_requirements": "teks...",
        "priority_attributes":  "teks...",
        "required_documents":   "teks..."
    }
    """
    result = {key: "-" for key in DROPDOWN_KEYS}

    # Temukan semua accordion dengan id="content-accordion"
    accordions = soup.find_all(
        "div", {"class": "accordion accordion-flush", "id": "content-accordion"}
    )

    if subclass_index >= len(accordions):
        logger.warning(
            f"  Accordion index {subclass_index} tidak ditemukan "
            f"(total accordion: {len(accordions)})"
        )
        return result

    target_accordion = accordions[subclass_index]

    # Tiap dropdown = 1 accordion-item
    items = target_accordion.find_all("div", class_="accordion-item")
    logger.info(f"  Accordion[{subclass_index}] → {len(items)} dropdown item ditemukan")

    for i, item in enumerate(items):
        if i >= len(DROPDOWN_KEYS):
            break  # hanya ambil 3 dropdown yang diinginkan

        # Ambil konten dari accordion-body (sudah ter-expand oleh Playwright)
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
    Ketiga field (minimum_requirements, priority_attributes, required_documents)
    digabung menjadi 1 teks per pathway.

    Accordion index per subclass dikontrol via PATHWAY_SUBCLASS_INDEX.
    Jika index = None, subclass tersebut tidak tersedia di pathway itu → diisi "-".

    Returns:
    {
        190: { "tse": "min req...\\npriority...\\ndocs...", "tsg": "...", "tbo": "-" },
        491: { "tse": "...", "tsg": "...", "tbo": "..." }
    }
    """
    all_data = {sc: {} for sc in SUBCLASSES}

    for pathway_name, url in pathway_urls.items():
        logger.info(f"\n=== Pathway: {pathway_name.upper()} ===")
        soup = fetch_and_expand_accordions(url)

        if not soup:
            logger.error(f"  Skip pathway {pathway_name} — gagal fetch")
            for sc in SUBCLASSES:
                all_data[sc][pathway_name] = "-"
            continue

        # Ambil mapping index untuk pathway ini
        index_map = PATHWAY_SUBCLASS_INDEX.get(
            pathway_name, {sc: i for i, sc in enumerate(SUBCLASSES)}
        )

        for subclass in SUBCLASSES:
            accordion_index = index_map.get(subclass)

            # Jika None → subclass tidak tersedia di pathway ini
            if accordion_index is None:
                logger.info(
                    f"  Subclass {subclass} tidak tersedia di pathway {pathway_name} → '-'"
                )
                all_data[subclass][pathway_name] = "-"
                continue

            logger.info(
                f"  Parsing subclass {subclass} (accordion index {accordion_index})"
            )
            section_data = parse_subclass_section(soup, subclass_index=accordion_index)

            # Gabungkan 3 field menjadi 1 teks dengan label section
            combined_parts = []
            labels = {
                "minimum_requirements": "Minimum Requirements",
                "priority_attributes": "Priority Attributes",
                "required_documents": "Required Documents",
            }
            for key in DROPDOWN_KEYS:
                value = section_data.get(key, "-")
                combined_parts.append(f"[{labels[key]}]\n{value}")

            all_data[subclass][pathway_name] = "\n\n".join(combined_parts)

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
        row.update(all_data[subclass])  # langsung: tse, tsg, ter, tbo  
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
