"""
NSW Scraper — New South Wales Skills List (main & regional).

Berdasarkan HTML asli dari:
https://www.nsw.gov.au/visas-and-migration/skilled-visas/nsw-skills-lists

Struktur halaman:
  - nsw-table-1  → Visa 190 (Skills List)
  - nsw-table-2  → Visa 491 (Regional Skills List)

Jika ANZSCO code muncul di kedua tabel → visa_190=True AND visa_491=True.
"""

import logging
from typing import Dict, List

from bs4 import BeautifulSoup

from .base_scraper import make_raw_record
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

# ── Konstanta ID tabel sesuai struktur HTML NSW ───────────────────────────────
TABLE_190_ID = "nsw-table-1"
TABLE_491_ID = "nsw-table-2"

HEADER_KEYWORDS = {"anzsco code", "unit group name", "code", "occupation"}


# ── Helper ────────────────────────────────────────────────────────────────────

def _is_header_row(cells: list) -> bool:
    """True jika row adalah baris header (bukan data)."""
    return any(cell.get_text(strip=True).lower() in HEADER_KEYWORDS for cell in cells)


def _extract_table(soup: BeautifulSoup, table_id: str) -> Dict[str, str]:
    """
    Parse tabel berdasarkan ID → return dict {anzsco_code: occupation_name}.
    Kolom pertama = ANZSCO Code, kolom kedua = Unit Group Name.
    """
    result: Dict[str, str] = {}

    table = soup.find("table", {"id": table_id})
    if not table:
        logger.warning(f"[NSW] Tabel dengan id='{table_id}' tidak ditemukan.")
        return result

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        if _is_header_row(cells):
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(separator=" ", strip=True)

        # Validasi: code harus numerik (4 digit ANZSCO unit group)
        if not code.isdigit() or not (3 <= len(code) <= 6):
            logger.debug(f"[NSW] Skip baris tidak valid: code='{code}' name='{name}'")
            continue

        if not name:
            logger.debug(f"[NSW] Skip baris tanpa nama: code='{code}'")
            continue

        result[code] = name

    logger.debug(f"[NSW] Tabel '{table_id}' → {len(result)} entri.")
    return result


# ── Merge logic ───────────────────────────────────────────────────────────────

def _merge_tables(
    data_190: Dict[str, str],
    data_491: Dict[str, str],
    state: str,
    list_type: str,
) -> List[dict]:
    """
    Gabungkan data dari dua tabel.
    Jika ANZSCO code muncul di kedua tabel → visa_190=True & visa_491=True.
    """
    all_codes = set(data_190.keys()) | set(data_491.keys())
    records = []

    for code in sorted(all_codes):
        in_190 = code in data_190
        in_491 = code in data_491

        # Ambil nama: prioritaskan tabel 190, fallback ke 491
        name = data_190.get(code) or data_491.get(code)

        records.append(make_raw_record(
            state=state,
            list_type=list_type,
            raw_code=code,
            raw_name=name,
            visa_190=in_190,
            visa_491=in_491,
        ))

        if in_190 and in_491:
            logger.debug(f"[NSW] Code {code} ('{name}') ada di KEDUA tabel → 190+491")

    return records


# ── Parser utama ──────────────────────────────────────────────────────────────

def _parse_nsw_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")

    data_190 = _extract_table(soup, TABLE_190_ID)
    data_491 = _extract_table(soup, TABLE_491_ID)

    if not data_190 and not data_491:
        logger.error("[NSW] Kedua tabel kosong — struktur HTML mungkin berubah.")
        logger.error(
            f"[NSW] Periksa apakah ID tabel masih '{TABLE_190_ID}' dan '{TABLE_491_ID}'."
        )
        return []

    overlap = set(data_190.keys()) & set(data_491.keys())
    logger.info(
        f"[NSW] Tabel 190: {len(data_190)} entri | "
        f"Tabel 491: {len(data_491)} entri | "
        f"Overlap (keduanya): {len(overlap)} entri"
    )

    records = _merge_tables(data_190, data_491, state, list_type)
    logger.info(f"[NSW] Total {len(records)} records unik setelah merge.")
    return records


# ── Entry point publik ────────────────────────────────────────────────────────

def scrape(
    url: str,
    state: str = "NSW",
    list_type: str = "main",
    headless: bool = True,
) -> List[dict]:
    """Scrape NSW Skills List page dan return list raw records."""
    logger.info(f"[NSW] Scraping dari: {url}")
    html = get_page_source_playwright(url=url, wait_for_selector="table", bypass_cf=False)
    # html = get_page_source(url, headless=headless, wait_seconds=5, force_selenium=True)
    if not html:
        logger.warning(f"[NSW] Tidak ada HTML yang didapat dari {url}")
        return []
    return _parse_nsw_html(html, state, list_type)