""" QLD State Visa Requirements Scraper

Alur kerja Function:

__main__
  ├── scrape_qld_pathway("Workers_Living_in_Queensland", url)
  │     ├── fetch_and_parse(url)                    → BeautifulSoup container (component_*)
  │     ├── extract_detail_requirements(container)   → teks dari tabel Migration QLD requirements
  │     └── extract_service_fee(soup)                → list nilai $xxx
  │
  ├── scrape_qld_pathway("Workers_Living_Offshore", url)
  ├── scrape_qld_pathway("Building_and_Construction", url)
  ├── scrape_qld_pathway("University_Graduates", url)
  │
  ├── scrape_qld_business(url)                      → 3 baris (general, pathway 1, pathway 2)
  │     ├── fetch_and_parse(url)
  │     ├── parse_requirement_table(tbody)  ×3
  │     └── extract_service_fee(soup)
  │
  ├── pd.concat([...])                              → gabung jadi 1 DataFrame (7 baris)
  │
  └── export_dataframe(final_df, ...)               → CSV + JSON + formatted XLSX
"""

import logging
import os
import re

import pandas as pd
from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright
from general_tools_scrap import (
    get_clean_text,
    extract_service_fee,
    export_dataframe,
)



# Output path relative to this script location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "qld")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ── Fetch ─────────────────────────────────────────────────────────────────────


def fetch_and_parse(url, component_id=None):
    """Fetch HTML dan return (container, soup).

    container : BeautifulSoup element — div utama konten QLD (component_*)
    soup      : BeautifulSoup — full page soup untuk extract_service_fee

    Parameters
    ----------
    url          : str — URL halaman QLD
    component_id : str | None — ID spesifik container (misal 'component_1540893').
                   Jika None, cari div yang id-nya dimulai 'component_'.
    """
    logger.info(f"Fetching: {url}")
    html = get_page_source_playwright(
        url=url,
        wait_for_selector="body",
        extra_wait_seconds=3,
        bypass_cf=False,
    )
    if not html:
        logger.error("Gagal mendapatkan HTML.")
        return None, None

    soup = BeautifulSoup(html, "lxml")

    # Cari container utama
    if component_id:
        container = soup.find("div", id=component_id)
    else:
        container = soup.find("div", id=lambda x: x and x.startswith("component_"))

    if not container:
        container = soup.find("body")
        logger.warning("Container 'component_*' tidak ditemukan, fallback ke <body>.")

    # Hapus elemen navigasi/menu/footer agar tidak ikut ter-scrape
    for bad in container.find_all(["nav", "header", "footer", "aside"]):
        bad.decompose()

    nav_like = re.compile(
        r"nav|menu|breadcrumb|masthead|site-header|site-footer|skip|primary",
        re.I,
    )
    for el in container.find_all(True):
        attrs = getattr(el, "attrs", None)
        if not attrs:
            continue
        classes = attrs.get("class") or []
        el_id = attrs.get("id", "") or ""
        try:
            if any(nav_like.search(c) for c in classes) or nav_like.search(el_id):
                el.decompose()
        except Exception:
            continue

    return container, soup


# ── Parsing Helpers ───────────────────────────────────────────────────────────


def parse_requirement_table(tbody):
    """Parse satu <tbody> tabel requirement QLD.

    Format tabel QLD: kolom 1 = judul requirement, kolom 2 = detail eligibility.
    Menghasilkan teks multi-line dengan bullet points.
    """
    lines = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        header = cells[0].get_text(" ", strip=True)
        value_cell = cells[1]

        if header:
            lines.append(header)

        for tag in value_cell.find_all(["p", "li"]):
            text = tag.get_text(" ", strip=True)
            if text:
                lines.append(f"- {text}")

    return "\n".join(lines).strip()




def extract_detail_requirements(container):
    """Ekstrak bagian 'Migration Queensland requirements' dari tabel.

    QLD halaman pathway menyimpan detail requirements dalam <tbody>.
    Jika ada tabel, parse tabel. Jika tidak, fallback ke get_clean_text().
    """
    if not container:
        return ""

    # Cari semua tbody — untuk halaman standar biasanya ada 1 tabel requirements
    tbodies = container.find_all("tbody")
    if tbodies:
        # Untuk halaman standar (bukan business), ambil tabel pertama
        return parse_requirement_table(tbodies[0])

    # Fallback: ambil konten dari bagian 'Migration Queensland requirements'
    for heading in container.find_all(["h3", "h4"]):
        if "migration queensland" in heading.get_text(strip=True).lower():
            from bs4 import BeautifulSoup as BS

            wrapper = BS("<div></div>", "lxml").find("div")
            sibling = heading.find_next_sibling()
            while sibling:
                if sibling.name in ["h2", "h3"]:
                    break
                wrapper.append(sibling.__copy__())
                sibling = sibling.find_next_sibling()

            text = get_clean_text(wrapper)
            if text:
                return text

    # Fallback terakhir: get_clean_text pada seluruh container
    return get_clean_text(container)


# ── Scraper Utama ─────────────────────────────────────────────────────────────


def scrape_qld_pathway(stream_name, url, component_id=None):
    """Scrape QLD visa requirements untuk satu pathway.

    Parameters
    ----------
    stream_name  : str — nama pathway (misal: "Workers_Living_in_Queensland")
    url          : str — URL halaman QLD
    component_id : str | None — ID spesifik container jika halaman punya id unik

    Returns
    -------
    pd.DataFrame — 1 baris dengan kolom:
        state code, state stream, Detail Requirements, service fee
    """
    logger.info(f"=== Scraping QLD: {stream_name} ===")
    container, soup = fetch_and_parse(url, component_id=component_id)
    if not container:
        return pd.DataFrame()

    text_detail = extract_detail_requirements(container)

    fees = extract_service_fee(soup)
    service_fee_val = ", ".join(sorted(set(fees))) if fees else "-"

    data = {
        "state code": "QLD",
        "state stream": stream_name,
        "Detail Requirements": text_detail,
        "service fee": service_fee_val,
    }

    return pd.DataFrame([data])

def scrape_qld_business(url):
    """Scrape halaman QLD Small Business Owners (3 tabel).

    Halaman business memiliki 3 tabel terpisah:
      1. General eligibility criteria
      2. Pathway 1 — Business purchase
      3. Pathway 2 — Start-up business

    Returns
    -------
    pd.DataFrame — 3 baris, satu per tabel
    """
    logger.info("=== Scraping QLD: Small_Business_Owners ===")
    container, soup = fetch_and_parse(url)
    if not container:
        return pd.DataFrame()

    # Parse 3 tabel business
    tbodies = container.find_all("tbody")

    table_general = parse_requirement_table(tbodies[0]) if len(tbodies) >= 1 else ""
    table_pathway1 = parse_requirement_table(tbodies[1]) if len(tbodies) >= 2 else ""
    table_pathway2 = parse_requirement_table(tbodies[2]) if len(tbodies) >= 3 else ""

    if len(tbodies) < 3:
        logger.warning(
            f"Hanya ditemukan {len(tbodies)} tabel (diharapkan 3) "
            f"di halaman business."
        )

    fees = extract_service_fee(soup)
    service_fee_val = ", ".join(sorted(set(fees))) if fees else "-"

    rows = [
        {
            "state code": "QLD",
            "state stream": "Small_Business_Owners",
            "Detail Requirements": table_general,
            "service fee": service_fee_val,
        },
        {
            "state code": "QLD",
            "state stream": "Small_Business_Pathway_1_Purchase",
            "Detail Requirements": table_pathway1,
            "service fee": service_fee_val,
        },
        {
            "state code": "QLD",
            "state stream": "Small_Business_Pathway_2_Startup",
            "Detail Requirements": table_pathway2,
            "service fee": service_fee_val,
        },
    ]

    return pd.DataFrame(rows)


# ── Export ────────────────────────────────────────────────────────────────────


def export_results(df):
    """Export hasil scraping QLD ke CSV, JSON, dan formatted XLSX."""
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_qld",
        preview_columns=["state code", "state stream", "service fee"],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Pathway 1: Workers Living in Queensland (Onshore) ─────────────────
    df_onshore = scrape_qld_pathway(
        stream_name="Workers_Living_in_Queensland",
        url="https://migration.qld.gov.au/visa-options/skilled-visas/skilled-workers-living-in-queensland",
    )

    # ── Pathway 2: Workers Living Offshore ────────────────────────────────
    df_offshore = scrape_qld_pathway(
        stream_name="Workers_Living_Offshore",
        url="https://migration.qld.gov.au/visa-options/skilled-visas/skilled-workers-living-offshore",
    )

    # ── Pathway 3: Building and Construction Workers ──────────────────────
    df_building = scrape_qld_pathway(
        stream_name="Building_and_Construction",
        url="https://migration.qld.gov.au/visa-options/skilled-visas/building-and-construction-workers",
    )

    # ── Pathway 4: Queensland University Graduates ────────────────────────
    df_university = scrape_qld_pathway(
        stream_name="University_Graduates",
        url="https://www.migration.qld.gov.au/visa-options/skilled-visas/graduates-of-a-queensland-university",
        component_id="component_1540893",
    )

    # ── Pathway 5: Small Business Owners (3 tabel) ────────────────────────
    df_business = scrape_qld_business(
        url="https://migration.qld.gov.au/visa-options/skilled-visas/small-business-owners-operating-in-regional-queensland",
    )

    # Gabungkan & export
    final_df = pd.concat(
        [df_onshore, df_offshore, df_building, df_university, df_business],
        ignore_index=True,
    )
    export_results(final_df)