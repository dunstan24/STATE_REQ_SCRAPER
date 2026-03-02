"""
QLD Scraper — Queensland Skilled Occupation List.

Struktur tabel (1 tabel, 5 kolom):
  | ANZSCO Code | Occupation | 491 | 190 | Building & Construction pathway |

Kolom urutan: col[0]=code, col[1]=name, col[2]=491, col[3]=190, col[4]=building_pathway

Logika visa:
  - visa_491 = True jika col[2] berisi "yes" (case-insensitive)
  - visa_190 = True jika col[3] berisi "yes"
  - building_pathway = True jika col[4] berisi "yes" (disimpan sebagai extra field)

Tidak ada Cloudflare → force_selenium=True (butuh JS render).
"""

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base_scraper import make_raw_record
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

# Regex validasi ANZSCO code (6 digit)
_ANZSCO_RE = re.compile(r"^\d{6}$")

# Indeks kolom berdasarkan struktur HTML yang dianalisis
_COL_CODE     = 0
_COL_NAME     = 1
_COL_491      = 2
_COL_190      = 3
_COL_BUILDING = 4


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cell_text(cells: list, idx: int) -> str:
    """Ambil text dari cell pada index tertentu, return '' jika tidak ada."""
    if idx >= len(cells):
        return ""
    return cells[idx].get_text(separator=" ", strip=True)


def _is_yes(text: str) -> bool:
    """Return True jika cell berisi 'yes' (case-insensitive)."""
    return text.strip().lower() == "yes"


def _is_header_row(cells: list) -> bool:
    """True jika baris adalah header (berisi teks seperti 'ANZSCO', 'Occupation', dll)."""
    if not cells:
        return False
    first = cells[0].get_text(strip=True).lower()
    return any(kw in first for kw in ("anzsco", "code", "occupation"))


def _detect_columns(table) -> Optional[dict]:
    """
    Fallback: deteksi indeks kolom dari header jika struktur berubah.
    Return dict {code, name, v491, v190, building} atau None jika gagal.
    """
    thead = table.find("thead")
    if not thead:
        return None

    headers = [th.get_text(separator=" ", strip=True).lower()
               for th in thead.find_all("th")]

    def find(keywords):
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    col_code     = find(["anzsco", "code"])
    col_name     = find(["occupation", "title"])
    col_491      = find(["491"])
    col_190      = find(["190"])
    col_building = find(["building", "construction", "pathway"])

    if col_code is None or col_name is None:
        return None

    return {
        "code":     col_code,
        "name":     col_name,
        "v491":     col_491,
        "v190":     col_190,
        "building": col_building,
    }


# ── Core parser ───────────────────────────────────────────────────────────────

def _parse_qld_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []

    tables = soup.find_all("table")
    if not tables:
        logger.warning("[QLD] Tidak ada <table> ditemukan di halaman.")
        return records

    logger.info(f"[QLD] Ditemukan {len(tables)} tabel — memproses semua.")

    for t_idx, table in enumerate(tables):
        # Coba deteksi kolom dari header sebagai fallback
        col_map = _detect_columns(table)
        if col_map:
            ci_code     = col_map["code"]
            ci_name     = col_map["name"]
            ci_491      = col_map["v491"]
            ci_190      = col_map["v190"]
            ci_building = col_map["building"]
            logger.info(
                f"[QLD] Tabel {t_idx+1}: kolom terdeteksi dari header — "
                f"code={ci_code}, name={ci_name}, 491={ci_491}, "
                f"190={ci_190}, building={ci_building}"
            )
        else:
            # Gunakan indeks tetap berdasarkan struktur yang dianalisis
            ci_code, ci_name = _COL_CODE, _COL_NAME
            ci_491, ci_190   = _COL_491, _COL_190
            ci_building      = _COL_BUILDING
            logger.info(
                f"[QLD] Tabel {t_idx+1}: header tidak terdeteksi — "
                f"pakai indeks default (code=0, name=1, 491=2, 190=3, building=4)"
            )

        tbody = table.find("tbody") or table
        rows = tbody.find_all("tr")
        table_count = 0

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells or len(cells) < 2:
                continue
            if _is_header_row(cells):
                continue

            raw_code = _cell_text(cells, ci_code)
            raw_name = _cell_text(cells, ci_name)

            # Bersihkan kode: ambil hanya 6 digit pertama
            code_clean = re.sub(r"[^\d]", "", raw_code)
            if not _ANZSCO_RE.match(code_clean):
                # Coba cari ANZSCO code di kolom lain jika kolom utama kosong/invalid
                for cell in cells:
                    candidate = re.sub(r"[^\d]", "", cell.get_text(strip=True))
                    if _ANZSCO_RE.match(candidate):
                        code_clean = candidate
                        break

            if not code_clean and not raw_name:
                continue  # skip baris kosong

            # Visa eligibility
            text_491      = _cell_text(cells, ci_491)      if ci_491      is not None else ""
            text_190      = _cell_text(cells, ci_190)      if ci_190      is not None else ""
            text_building = _cell_text(cells, ci_building) if ci_building is not None else ""

            visa_491      = _is_yes(text_491)
            visa_190      = _is_yes(text_190)
            building_path = _is_yes(text_building)

            records.append(make_raw_record(
                state=state,
                list_type=list_type,
                raw_code=code_clean or None,
                raw_name=raw_name or None,
                visa_190=visa_190,
                visa_491=visa_491,
                building_construction_pathway=building_path,
            ))
            table_count += 1

        logger.info(f"[QLD] Tabel {t_idx+1}: {table_count} records diambil.")

    v190  = sum(1 for r in records if r["visa_190"])
    v491  = sum(1 for r in records if r["visa_491"])
    build = sum(1 for r in records if r.get("building_construction_pathway"))
    logger.info(
        f"[QLD] Total: {len(records)} records | "
        f"190: {v190} | 491: {v491} | Building pathway: {build}"
    )
    return records


# ── Entry point ───────────────────────────────────────────────────────────────

def scrape(
    url: str,
    state: str = "QLD",
    list_type: str = "onshore",
    headless: bool = True,
) -> List[dict]:
    """
    Scrape QLD Skilled Occupation List dan return list raw records.

    QLD tidak menggunakan Cloudflare tapi membutuhkan JS rendering
    → force_selenium=True.
    """
    logger.info(f"[QLD] Scraping {list_type} dari: {url}")
    html = get_page_source_playwright(
        url,
        extra_wait_seconds=20,
        wait_for_selector="table",
        bypass_cf=False,
    )
    if not html:
        logger.warning(f"[QLD] Tidak ada HTML dari: {url}")
        return []

    return _parse_qld_html(html, state, list_type)