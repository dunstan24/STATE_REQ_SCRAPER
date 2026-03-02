"""
TAS Scraper — Tasmania Subclass 190 TSE Priority Roles.

Source: https://www.migration.tas.gov.au/skilled_migration/
        subclass-190-tasmanian-skilled-employment-tse-priority-roles

HTML structure: standard <table> with 3 columns:
  Col 0: TSE Priority Occupations (eligible skills assessments)
          → one or more "XXXXXX Occupation Name" lines in bold, per cell
  Col 1: Examples of related roles — NOW SCRAPED
          → plain text lines containing 6-digit codes are extracted
  Col 2: Notes and caveats (optional caveat text, may be empty)

Logic:
  - Extract Col 0 codes/names (primary eligible occupations)
    → visa_190 = True
  - ALSO extract Col 1 codes/names, but ONLY entries that have a 6-digit code
    → visa_190 = True (URL is specific to 190 visa, all occupations qualify)
    → Skip if code already captured from Col 0 (no duplicates)
  - One table row may contain multiple occupations → explode to individual records
  - visa_491 = False (491 OSOP pathway closed for 2025-26, no occupation list)
  - notes = Col 2 text (shared across all occupations in the same row)
  - Deduplicate by occupation_code (last row has duplicate entries)

Normalisation note:
  Occupation names in Col 0 sometimes have format variations like
  "Nurses nec" or "Manager / Director" — normalised via _clean_name().
"""

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from .base_scraper import make_raw_record
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

# Matches "123456 Occupation Name" pattern
_OCC_LINE_RE = re.compile(r"^(\d{6})\s+(.+)$")


def scrape(url: str, state: str = "TAS", list_type: str = "main",
           headless: bool = True) -> List[dict]:
    """Scrape TAS TSE Priority Roles page and return raw records."""
    logger.info(f"[TAS] Scraping {list_type} list from: {url}")
    html = get_page_source_playwright(url=url, wait_for_selector="table", extra_wait_seconds=6, bypass_cf=False)
    if not html:
        logger.warning(f"[TAS] No HTML retrieved from {url}")
        return []
    return _parse_tas_html(html, state, list_type)


def _parse_tas_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")

    # Find the main data table — only one <table> on this page
    table = soup.find("table")
    if not table:
        logger.warning("[TAS] No <table> found on page.")
        return []

    records = []
    seen_codes = set()  # for deduplication across col 0 AND col 1

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue  # skip header row (uses <th>) or malformed rows

        col0 = cells[0]  # TSE Priority Occupations — source of truth
        col1 = cells[1]  # Examples of related roles
        col2 = cells[2]  # Notes and caveats

        # Extract notes text from col 2 (strip whitespace, may be empty)
        notes = _clean_notes(col2.get_text(separator=" ", strip=True))

        # --- Col 0: primary eligible occupations, visa_190 = True ---
        for code, name in _extract_priority_occupations(col0):
            if code in seen_codes:
                continue
            seen_codes.add(code)

            record = make_raw_record(
                state=state,
                list_type=list_type,
                raw_code=code,
                raw_name=name,
                visa_190=True,   # This IS the 190 priority list
                visa_491=False,  # 491 OSOP closed for 2025-26
            )
            record["notes"] = notes
            records.append(record)

        # --- Col 1: related roles ---
        # Only extract entries that have a 6-digit ANZSCO code.
        # Skip codes already seen from Col 0 (avoid duplicates).
        # visa_190 = True because this URL is specific to the 190 visa list.
        for code, name in _extract_related_roles(col1):
            if code in seen_codes:
                continue
            seen_codes.add(code)

            record = make_raw_record(
                state=state,
                list_type=list_type,
                raw_code=code,
                raw_name=name,
                visa_190=True,   # URL is 190-specific, all occupations qualify
                visa_491=False,
            )
            record["notes"] = notes
            records.append(record)

    col0_count = sum(1 for r in records if r.get("visa_190"))
    col1_count = sum(1 for r in records if not r.get("visa_190"))
    logger.info(
        f"[TAS] Extracted {len(records)} records "
        f"(col0={col0_count} primary, col1={col1_count} related roles)."
    )
    return records


def _extract_priority_occupations(cell: Tag) -> List[tuple]:
    """
    Extract (code, name) pairs from Col 0 of a table row.

    Col 0 structure example:
      <td>
        <strong>121311 Apiarist</strong><br>
        <strong>121321 Poultry Farmer</strong>
      </td>

    Only <strong> or <b> tagged text is the "eligible" occupation.
    Non-bold text is just label/context — skip it.
    """
    results = []

    # Strategy 1: extract from <strong> or <b> tags (primary pattern)
    bold_tags = cell.find_all(["strong", "b"])
    for tag in bold_tags:
        text = tag.get_text(separator=" ", strip=True)
        # A bold tag might contain multiple lines separated by <br>
        for line in _split_lines(text):
            match = _OCC_LINE_RE.match(line.strip())
            if match:
                code = match.group(1)
                name = _clean_name(match.group(2))
                results.append((code, name))

    # Strategy 2: if no bold tags found, try all text lines (fallback)
    if not results:
        full_text = cell.get_text(separator="\n", strip=True)
        for line in full_text.splitlines():
            line = line.strip()
            match = _OCC_LINE_RE.match(line)
            if match:
                code = match.group(1)
                name = _clean_name(match.group(2))
                results.append((code, name))

    return results


def _extract_related_roles(cell: Tag) -> List[tuple]:
    """
    Extract (code, name) pairs from Col 1 of a table row.

    Col 1 contains plain-text examples of related roles.
    Only lines/entries that contain a 6-digit ANZSCO code are kept.

    Col 1 may be structured as:
      - Plain text lines: "123456 Occupation Name"
      - Bullet list items (<li>): "123456 Occupation Name"
      - Bold tags (<strong>/<b>): same pattern
      - Mixed inline text with codes embedded anywhere

    Strategy: scan ALL text lines (including list items and bold),
    extract any match for _OCC_LINE_RE.
    """
    results = []
    seen_in_cell = set()  # deduplicate within the same col 1 cell

    # Use "\n" separator so <br>, <li>, <p> boundaries become line breaks
    full_text = cell.get_text(separator="\n", strip=True)

    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _OCC_LINE_RE.match(line)
        if match:
            code = match.group(1)
            if code in seen_in_cell:
                continue
            seen_in_cell.add(code)
            name = _clean_name(match.group(2))
            results.append((code, name))

    return results


def _split_lines(text: str) -> List[str]:
    """Split text that may have been joined with spaces or newlines."""
    # After get_text(), <br> become spaces or newlines depending on parser
    # Try splitting on digit boundary: "123456 Name 234567 Name2" → two entries
    # First try newline split
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 1:
        return lines

    # Fallback: split on pattern "digits space" preceded by text
    # e.g. "121311 Apiarist 121321 Poultry Farmer"
    parts = re.split(r"(?<=\w)\s+(?=\d{6}\s)", text)
    return [p.strip() for p in parts if p.strip()]


def _clean_name(name: str) -> str:
    """Normalise occupation name — collapse whitespace, fix slash spacing."""
    name = re.sub(r"\s+", " ", name).strip()
    # Normalise " / " slashes (sometimes "Manager / Director" vs "Manager/Director")
    name = re.sub(r"\s*/\s*", " / ", name)
    return name


def _clean_notes(notes: str) -> Optional[str]:
    """Return None if notes cell is empty, otherwise return cleaned text."""
    if not notes or notes.strip() in ("", "-"):
        return None
    return re.sub(r"\s+", " ", notes).strip()