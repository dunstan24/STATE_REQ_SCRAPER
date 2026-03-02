"""
SA Scraper — South Australia skilled occupation list.

HTML structure (dari migration.sa.gov.au/occupation-list):

  div[data-occupation-id="001-1"
      data-occupation-anzsco="131112"
      data-occupation-title="Sales and Marketing Manager"]
    │
    ├── child: "Applying from: South Australia"
    │     └── stream entries (SA Graduates / Skilled Employment / Outer Regional)
    │           Subclass: [190] [491]  ← anchor text "190" / "491"
    │
    └── child: "Applying from: Offshore"
          └── stream entry
                Subclass: [190] [491]   ← ada, atau
                teks: "This occupation is not available to offshore clients."

Key insight:
  - ANZSCO code & occupation title ada di data-attribute <div data-occupation-anzsco="...">
  - visa_190/491 ditentukan dari subclass links di bagian "South Australia" context
  - offshore_available = False jika teks "not available to offshore clients" ditemukan
  - offshore_190/491 dari subclass links di bagian "Offshore" context
"""

# TODO make sure schema about 419 & 190
import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from .base_scraper import make_raw_record
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

_ANZSCO_RE  = re.compile(r"ANZSCO\s+(\d{4,6})", re.IGNORECASE)
_CODE_RE    = re.compile(r"\b(\d{6})\b")
_NOT_AVAIL  = re.compile(r"not available to offshore", re.IGNORECASE)


def scrape(url: str, state: str = "SA", list_type: str = "main",
           headless: bool = True) -> List[dict]:
    """Scrape a SA occupation list page and return raw records."""
    logger.info(f"[SA] Scraping {list_type} list from: {url}")
    html = get_page_source_playwright(url=url, wait_for_selector="div[data-occupation-anzsco]", extra_wait_seconds=8, bypass_cf=False)
    if not html:
        logger.warning(f"[SA] No HTML retrieved from {url}")
        return []
    return _parse_sa_html(html, state, list_type)


def _parse_sa_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []

    # --- Primary strategy: data-occupation-anzsco attribute ---
    # Each occupation is wrapped in a div with data-occupation-anzsco
    occupation_divs = soup.find_all("div", attrs={"data-occupation-anzsco": True})

    if occupation_divs:
        logger.info(f"[SA] Found {len(occupation_divs)} occupation divs via data-attribute strategy.")
        for div in occupation_divs:
            record = _parse_occupation_div(div, state, list_type)
            if record:
                records.append(record)
    else:
        # --- Fallback: look for ANZSCO text pattern ---
        logger.warning("[SA] data-occupation-anzsco not found; trying ANZSCO text fallback.")
        records = _fallback_parse(soup, state, list_type)

    logger.info(f"[SA] Extracted {len(records)} records from {list_type} list.")
    return records


def _parse_occupation_div(div: Tag, state: str, list_type: str) -> Optional[dict]:
    """
    Parse a single occupation div (the outer parent accordion item).

    div attrs:
        data-occupation-anzsco="131112"
        data-occupation-title="Sales and Marketing Manager"
        data-occupation-category-id="001"
    """
    raw_code = div.get("data-occupation-anzsco", "").strip()
    raw_name = div.get("data-occupation-title", "").strip()

    if not raw_code and not raw_name:
        return None

    # Find all "child" sections (each child = one "Applying from" context)
    # Structure: div.child > button (contains "Applying from: ...") > accordion-content
    child_divs = div.find_all("div", class_="child")

    visa_190      = False
    visa_491      = False
    offshore_avail = None      # None = not seen yet
    offshore_190  = False
    offshore_491  = False
    min_points    = None
    skill_level   = None

    for child in child_divs:
        # Determine context: "South Australia" or "Offshore"
        context_text = _get_context(child)
        is_offshore = "offshore" in context_text.lower()

        # Get accordion content (the actual data inside)
        content = child.find("div", attrs={"data-accordion-content": True})
        if not content:
            continue

        content_text = content.get_text(separator=" ")

        # Check "not available" for offshore
        if is_offshore and _NOT_AVAIL.search(content_text):
            offshore_avail = False
            continue
        elif is_offshore:
            offshore_avail = True

        # Extract subclass numbers from anchor links within this content
        subclasses = _extract_subclasses(content)

        if is_offshore:
            offshore_190 = "190" in subclasses
            offshore_491 = "491" in subclasses
        else:
            # onshore — union across all streams
            if "190" in subclasses:
                visa_190 = True
            if "491" in subclasses:
                visa_491 = True

            # Extract min points and skill level (only need once)
            if min_points is None:
                min_points = _extract_min_points(content)
            if skill_level is None:
                skill_level = _extract_skill_level(content)

    record = make_raw_record(
        state=state,
        list_type=list_type,
        raw_code=raw_code,
        raw_name=raw_name,
        visa_190=visa_190,
        visa_491=visa_491,
    )

    # Attach SA-specific extra fields
    record["offshore_available"] = offshore_avail if offshore_avail is not None else True
    record["offshore_190"]       = offshore_190
    record["offshore_491"]       = offshore_491
    record["min_points"]         = min_points
    record["skill_level"]        = skill_level

    return record


def _get_context(child_div: Tag) -> str:
    """Extract 'Applying from' context label from child accordion button."""
    btn = child_div.find("button")
    if btn:
        return btn.get_text(separator=" ", strip=True)
    return ""


def _extract_subclasses(content: Tag) -> set:
    """
    Extract subclass numbers (190, 491) from anchor links inside content.
    SA uses <a>190</a> and <a>491</a> patterns.
    """
    subclasses = set()
    for a in content.find_all("a"):
        txt = a.get_text(strip=True)
        if txt in ("190", "491"):
            subclasses.add(txt)
    return subclasses


def _extract_min_points(content: Tag) -> Optional[int]:
    """Extract minimum points value from content block."""
    text = content.get_text(separator="\n")
    match = re.search(r"Minimum points\s*\n\s*(\d+)", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _extract_skill_level(content: Tag) -> Optional[str]:
    """Extract skill level value from content block."""
    text = content.get_text(separator="\n")
    match = re.search(r"Skill [Ll]evel\s*\n\s*(Skill level \d+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _fallback_parse(soup: BeautifulSoup, state: str, list_type: str) -> List[dict]:
    """
    Fallback: scan for ANZSCO text pattern when data-attributes not present.
    Less accurate but provides basic coverage.
    """
    records = []
    seen_codes = set()

    anzsco_elements = soup.find_all(string=_ANZSCO_RE)
    for elem in anzsco_elements:
        code_match = _ANZSCO_RE.search(str(elem))
        if not code_match:
            continue
        raw_code = code_match.group(1)
        if raw_code in seen_codes:
            continue
        seen_codes.add(raw_code)

        # Walk up to find occupation heading
        parent = elem.parent
        raw_name = None
        for _ in range(8):
            if parent is None:
                break
            heading = parent.find(["h2", "h3", "h4"])
            if heading and heading.get_text(strip=True):
                raw_name = heading.get_text(strip=True)
                break
            parent = parent.parent

        # Determine visa eligibility from surrounding section text
        section_text = parent.get_text(separator=" ") if parent else ""
        visa_190 = "190" in section_text
        visa_491 = "491" in section_text

        records.append(make_raw_record(
            state=state,
            list_type=list_type,
            raw_code=raw_code,
            raw_name=raw_name,
            visa_190=visa_190,
            visa_491=visa_491,
        ))

    logger.info(f"[SA] Fallback found {len(records)} records.")
    return records