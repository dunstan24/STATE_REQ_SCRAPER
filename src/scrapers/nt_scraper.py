"""
NT Scraper — Northern Territory offshore migration occupation list.

NT page is on australiasnorthernterritory.com.au which is a third-party
aggregator site. The table has id="table96564" with 3 columns:
ANZSCO | Occupation | Comments
"""

import logging
import re
from typing import List

from bs4 import BeautifulSoup

from .base_scraper import make_raw_record
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

_ANZSCO_RE = re.compile(r"\b(\d{6})\b")
_WHITESPACE_RE = re.compile(r"\s+")


def scrape(url: str, state: str = "NT", list_type: str = "main",
           headless: bool = True) -> List[dict]:
    """Scrape NT occupation list page and return raw records."""
    logger.info(f"[NT] Scraping list from: {url}")
    html = get_page_source_playwright(url=url, wait_for_selector="table", extra_wait_seconds=5, bypass_cf=False)
    if not html:
        logger.warning("[NT] No HTML retrieved from page.")
        return []
    return _parse_nt_html(html, state, list_type)


def _normalise(text: str) -> str:
    """Strip and collapse internal whitespace/nbsp."""
    return _WHITESPACE_RE.sub(" ", text.replace("\xa0", " ")).strip()


def _parse_nt_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []

    # ── Primary strategy: target the known table by id ──────────────────────
    table = soup.find("table", {"id": "table96564"})

    # Fallback: first table that has an ANZSCO-like header
    if table is None:
        for t in soup.find_all("table"):
            headers_text = t.get_text(" ").lower()
            if "anzsco" in headers_text and "occupation" in headers_text:
                table = t
                logger.debug("[NT] Fell back to first matching table.")
                break

    if table is None:
        logger.warning("[NT] No suitable table found — falling back to text scan.")
        return _fallback_text_scan(soup, state, list_type)

    # ── Resolve column indices from <th> text ────────────────────────────────
    header_row = table.find("thead")
    ths = header_row.find_all("th") if header_row else table.find_all("th")
    headers = [_normalise(th.get_text()).lower() for th in ths]

    code_idx     = _find_col(headers, ["anzsco", "code"])
    name_idx     = _find_col(headers, ["occupation", "title", "name"])
    comments_idx = _find_col(headers, ["comment", "note", "requirement"])

    # Hard-coded fallback for this specific table (ANZSCO=0, Occupation=1, Comments=2)
    if code_idx is None:
        code_idx = 0
    if name_idx is None:
        name_idx = 1
    if comments_idx is None and len(headers) >= 3:
        comments_idx = 2

    logger.debug(f"[NT] Column indices — code:{code_idx} name:{name_idx} comments:{comments_idx}")

    # ── Parse data rows ──────────────────────────────────────────────────────
    tbody = table.find("tbody") or table
    for row in tbody.find_all("tr"):
        cells = [_normalise(td.get_text()) for td in row.find_all(["td", "th"])]

        # Skip header rows that snuck into tbody, or rows with too few cells
        if len(cells) < 2:
            continue

        raw_code = _safe_get(cells, code_idx)
        raw_name = _safe_get(cells, name_idx)
        comments = _safe_get(cells, comments_idx) or ""

        # If code cell doesn't look like a 6-digit ANZSCO, skip (e.g. re-rendered header)
        if raw_code and not re.match(r"^\d{6}$", raw_code):
            logger.debug(f"[NT] Skipping non-ANZSCO row: {cells}")
            continue

        if not raw_code and not raw_name:
            continue

        # NT list has no separate 190/491 columns — all entries are for the
        # offshore nomination program; treat visa_190=True, visa_491=False
        # unless your pipeline differentiates by list_type elsewhere.
        record = make_raw_record(
            state=state,
            list_type=list_type,
            raw_code=raw_code,
            raw_name=raw_name,
            visa_190=True,
            visa_491=False,
        )

        # Attach licence requirement flag as extra metadata if comments present
        if comments:
            record["requires_licence"] = True
            record["licence_note"] = comments
        else:
            record["requires_licence"] = False
            record["licence_note"] = ""

        records.append(record)

    logger.info(f"[NT] Extracted {len(records)} records.")
    return records


def _fallback_text_scan(soup: BeautifulSoup, state: str, list_type: str) -> List[dict]:
    """Last-resort: pull 6-digit codes from plain text."""
    records = []
    text = soup.get_text(separator="\n")
    for match in _ANZSCO_RE.finditer(text):
        records.append(make_raw_record(
            state=state, list_type=list_type,
            raw_code=match.group(1), raw_name=None,
            visa_190=True, visa_491=False,
        ))
    logger.info(f"[NT] Fallback scan found {len(records)} codes.")
    return records


def _find_col(headers: list, keywords: list):
    for kw in keywords:
        for i, h in enumerate(headers):
            if kw in h:
                return i
    return None


def _safe_get(cells: list, idx):
    if idx is None or idx >= len(cells):
        return None
    v = cells[idx].strip()
    return v if v else None