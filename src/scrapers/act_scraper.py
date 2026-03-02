"""
ACT Scraper — Australian Capital Territory Nominated Occupation List.
Menggunakan Playwright + stealth untuk bypass Cloudflare Turnstile.
"""

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

# Import base scraper untuk state lain (make_raw_record tetap dari sini)
from .base_scraper import make_raw_record

# Import Playwright helper khusus ACT
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

# ── Konstanta ──────────────────────────────────────────────────────────────────
ANZSCO_CODE_RE = re.compile(r"^\d{6}$")
_491_ONLY_RE   = re.compile(r"\(491\s*only\)", re.IGNORECASE)
_190_ONLY_RE   = re.compile(r"\(190\s*only\)", re.IGNORECASE)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cell_text(td: Optional[Tag]) -> str:
    if td is None:
        return ""
    return td.get_text(separator=" ", strip=True)


def _detect_visa_flags(occupation_text: str) -> tuple[bool, bool]:
    if _491_ONLY_RE.search(occupation_text):
        return False, True   # visa_190=False, visa_491=True
    if _190_ONLY_RE.search(occupation_text):
        return True, False   # visa_190=True, visa_491=False
    return True, True


def _clean_occupation_name(text: str) -> str:
    text = _491_ONLY_RE.sub("", text)
    text = _190_ONLY_RE.sub("", text)
    return text.strip(" \t\n(),–-")


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_act_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")

    # Cari tabel berdasarkan konten header (aman dari perubahan ID)
    table = None
    for t in soup.find_all("table"):
        header_text = t.get_text().lower()
        if "anzsco unit group" in header_text and "nominated occupation" in header_text:
            table = t
            break

    if not table:
        with open("debug_act_no_table.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.error(
            "[ACT] Tabel tidak ditemukan setelah bypass CF! "
            "File debug_act_no_table.html telah dibuat untuk inspeksi manual."
        )
        return []

    # ── Parse tabel dengan rowspan handling ───────────────────────────────────
    rows = table.find_all("tr")
    records = []
    grid: List[List[str]] = []
    active_spans: dict[int, list] = {}

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        grid_row: List[str] = []
        cell_iter = iter(cells)

        for col_idx in range(4):
            if col_idx in active_spans:
                span_info = active_spans[col_idx]
                grid_row.append(span_info[1])
                span_info[0] -= 1
                if span_info[0] == 0:
                    del active_spans[col_idx]
            else:
                cell = next(cell_iter, None)
                if cell is None:
                    grid_row.append("")
                    continue

                text = _cell_text(cell)
                grid_row.append(text)

                rowspan = int(cell.get("rowspan", 1))
                if rowspan > 1:
                    active_spans[col_idx] = [rowspan - 1, text]

        grid.append(grid_row)

    # ── Grid → Records ────────────────────────────────────────────────────────
    for grid_row in grid:
        if len(grid_row) < 4:
            continue

        unit_group_name = grid_row[0].strip()
        unit_group_code = grid_row[1].strip()
        anzsco_code     = grid_row[2].strip()
        occupation_raw  = grid_row[3].strip()

        # Skip header rows
        if (
            "anzsco unit group" in unit_group_name.lower()
            or "nominated occupation" in occupation_raw.lower()
        ):
            continue

        # Validasi: ANZSCO harus 6 digit
        if not ANZSCO_CODE_RE.match(anzsco_code):
            continue

        visa_190, visa_491 = _detect_visa_flags(occupation_raw)
        clean_name = _clean_occupation_name(occupation_raw)

        records.append(make_raw_record(
            state=state,
            list_type=list_type,
            raw_code=anzsco_code,
            raw_name=clean_name,
            unit_group_code=unit_group_code,
            unit_group_name=unit_group_name,
            visa_190=visa_190,
            visa_491=visa_491,
        ))

    logger.info(f"[ACT] Berhasil mengambil {len(records)} records.")
    return records


# ── Entry Point ────────────────────────────────────────────────────────────────

def scrape(
    url: str,
    state: str = "ACT",
    list_type: str = "main",
    headless: bool = True,   # Parameter dipertahankan untuk kompatibilitas, tapi diabaikan
) -> List[dict]:
    """
    Entry point publik — dipanggil dari run_scraper.py.
    Parameter `headless` diabaikan karena Playwright selalu non-headless
    untuk melewati Cloudflare Turnstile.
    """
    logger.info(f"[ACT] Memulai scrape via Playwright+Stealth: {url}")

    if headless:
        logger.info(
            "[ACT] CATATAN: Parameter headless=True diabaikan. "
            "Playwright dijalankan non-headless (window tersembunyi di luar layar) "
            "agar bisa melewati Cloudflare Turnstile."
        )

    html = get_page_source_playwright(
        url=url,
        wait_for_selector="table",
        extra_wait_seconds=3,
        bypass_cf=True
    )

    if not html:
        logger.error("[ACT] Gagal mendapatkan HTML. Cek log di atas untuk detail.")
        return []

    return _parse_act_html(html, state, list_type)