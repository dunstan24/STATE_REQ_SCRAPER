"""
VIC Scraper — Victoria / Live in Melbourne nominated occupation list.

The VIC URL points to a registration-of-interest context that may not contain
a public occupation list. This scraper attempts to extract any occupation data
present and logs a warning if the page appears to be a form/ROI page only.
"""

import logging
import re
from typing import List

from bs4 import BeautifulSoup

from .base_scraper import make_raw_record
from .playwright_helper import get_page_source_playwright

logger = logging.getLogger(__name__)

_ANZSCO_RE = re.compile(r"\b(\d{6})\b")


def scrape(url: str, state: str = "VIC", list_type: str = "main",
           headless: bool = True) -> List[dict]:
    """Scrape VIC occupation list page and return raw records."""
    logger.info(f"[VIC] Scraping list from: {url}")
    html = get_page_source_playwright(url=url, wait_for_selector=None, extra_wait_seconds=6, bypass_cf=False)
    if not html:
        logger.warning("[VIC] No HTML retrieved from page.")
        return []
    return _parse_vic_html(html, state, list_type)


def _parse_vic_html(html: str, state: str, list_type: str) -> List[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []

    page_text = soup.get_text(separator="\n")

    # Detect if this is just a form/ROI page
    form_keywords = ["register your interest", "registration of interest", "submit", "contact us"]
    is_form = any(kw in page_text.lower() for kw in form_keywords)

    # Try tables
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        code_idx = _find_col(headers, ["anzsco", "code"])
        name_idx = _find_col(headers, ["occupation", "title", "name"])
        v190_idx = _find_col(headers, ["190"])
        v491_idx = _find_col(headers, ["491"])

        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            raw_code = _safe_get(cells, code_idx)
            raw_name = _safe_get(cells, name_idx)
            if not raw_code and not raw_name:
                continue
            if not raw_code:
                for c in cells:
                    if re.match(r"^\d{6}$", c.strip()):
                        raw_code = c.strip()
                        break
            v190 = _safe_get(cells, v190_idx) or ""
            v491 = _safe_get(cells, v491_idx) or ""
            records.append(make_raw_record(
                state=state, list_type=list_type,
                raw_code=raw_code, raw_name=raw_name,
                visa_190=_is_eligible(v190) if v190_idx is not None else True,
                visa_491=_is_eligible(v491) if v491_idx is not None else False,
            ))

    # Scan for inline ANZSCO codes in text
    if not records:
        for match in _ANZSCO_RE.finditer(page_text):
            records.append(make_raw_record(
                state=state, list_type=list_type,
                raw_code=match.group(1), raw_name=None,
                visa_190=True, visa_491=False,
            ))

    if not records and is_form:
        logger.warning(
            "[VIC] Page appears to be an ROI/contact form only — "
            "no occupation list data found. Consider checking for a different URL."
        )

    logger.info(f"[VIC] Extracted {len(records)} records.")
    return records


def _find_col(headers, keywords):
    for kw in keywords:
        for i, h in enumerate(headers):
            if kw in h:
                return i
    return None


def _safe_get(cells, idx):
    if idx is None or idx >= len(cells):
        return None
    v = cells[idx].strip()
    return v if v else None


def _is_eligible(text: str) -> bool:
    t = text.strip().lower()
    return t in {"yes", "y", "✓", "✔", "x", "●", "•"} or (t != "" and t not in {"no", "n", "–", "-", "×"})
