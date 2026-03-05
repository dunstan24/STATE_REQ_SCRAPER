import logging
import os
import pandas as pd
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from playwright_helper import get_page_source_playwright

# ==========================
# LINKS
# ==========================
URL_WA_190 = "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-nominated-190/points-table"
URL_WA_491 = "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-work-regional-provisional-491"

# ==========================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "wa")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_service_fee_from_soup(soup):
    keywords = ["service fee", "application fee"]
    fees = []
    for tag in soup.find_all(["p", "li", "td", "span", "div"]):
        text = tag.get_text(strip=True).lower()
        if any(kw in text for kw in keywords):
            fees.append(tag.get_text(strip=True))
    return fees


def export_dataframe(df, output_dir, filename_prefix, preview_columns=None):
    os.makedirs(output_dir, exist_ok=True)

    csv_path   = os.path.join(output_dir, f"{filename_prefix}.csv")
    json_path  = os.path.join(output_dir, f"{filename_prefix}.json")
    excel_path = os.path.join(output_dir, f"{filename_prefix}.xlsx")

    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_json(json_path, orient="records", force_ascii=False, indent=2)
    df.to_excel(excel_path, index=False)

    logger.info(f"Exported CSV   → {csv_path}")
    logger.info(f"Exported JSON  → {json_path}")
    logger.info(f"Exported Excel → {excel_path}")

    if preview_columns:
        logger.info("\n--- Preview ---")
        logger.info(df[preview_columns].to_string(index=False))


# ── 190 parser ─────────────────────────────────────────────────────────────────

def get_clean_text_190(soup):
    """Parse Angular ha-wysiwyg sections untuk halaman points table 190."""
    lines = []
    sections = soup.find_all("div", attrs={"tabindex": "-1"})

    for section in sections:
        h2 = section.find("h2")
        if h2:
            heading_text = h2.get_text(strip=True)
            if heading_text:
                lines.append(f"\n{heading_text.upper()}\n")

        content_div = section.find("ha-wysiwyg")
        if not content_div:
            continue

        edit_div = content_div.find("div", class_="edit-text")
        if not edit_div:
            continue

        for tag in edit_div.children:
            if not hasattr(tag, "name") or not tag.name:
                continue

            # ── Table: parse row by row with [Header] = value format ──────
            if tag.name == "table":
                headers = []
                for row in tag.find_all("tr"):
                    cells = row.find_all(["th", "td"])
                    if not cells:
                        continue

                    # Header row — collect column names
                    if all(c.name == "th" for c in cells):
                        headers = [c.get_text(" ", strip=True) for c in cells]
                        continue

                    # Data row — pair each cell with its header
                    values = [c.get_text(" ", strip=True) for c in cells]
                    if headers:
                        parts = [f"[{h}] = {v}" for h, v in zip(headers, values) if v]
                        if parts:
                            lines.append("   ".join(parts))
                    else:
                        # No headers found yet, fallback to plain values
                        lines.append("   ".join(v for v in values if v))
                continue

            # ── Non-table tags ─────────────────────────────────────────────
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            if tag.name == "li":
                lines.append(f"• {text}")
            elif tag.name in ["h3", "h4"]:
                lines.append(f"\n{text.upper()}\n")
            elif tag.name == "p":
                lines.append(text)
            # th/td outside a table — fallback (shouldn't normally occur)
            elif tag.name == "th":
                lines.append(f"[{text}]")
            elif tag.name == "td":
                lines.append(f"  {text}")

    return "\n".join(lines).strip()


# ── 491 parser ─────────────────────────────────────────────────────────────────

def get_clean_text_491(soup):
    """
    Parse halaman 491 — ambil heading + bullet points dari
    SEMUA ha-visa-card (Main applicant + Subsequent entrant),
    gabungkan jadi satu teks.
    """
    lines = []

    # Setiap card = satu visa type (Main / Subsequent)
    cards = soup.find_all("ha-visa-card")

    # Fallback jika Angular belum render ha-visa-card
    if not cards:
        cards = soup.find_all("div", class_="card")

    for card in cards:
        # Ambil heading card (h2 atau h3)
        heading = card.find(["h2", "h3"])
        if heading:
            heading_text = heading.get_text(strip=True)
            if heading_text:
                lines.append(f"\n{heading_text.upper()}\n")

        # Ambil semua bullet points di dalam card
        bullets = card.find_all("li")
        for li in bullets:
            text = li.get_text(strip=True)
            if text:
                lines.append(f"• {text}")

    return "\n".join(lines).strip()


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_and_parse(url, wait_for_selector="ha-wysiwyg"):
    logger.info(f"Fetching: {url}")

    html = get_page_source_playwright(
        url=url,
        wait_for_selector=wait_for_selector,
        extra_wait_seconds=5,
        bypass_cf=True,
    )

    if not html:
        logger.error("HTML tidak didapat.")
        return None

    # Debug — simpan HTML mentah
    slug = url.rstrip("/").split("/")[-1]
    debug_path = os.path.join(_SCRIPT_DIR, f"debug_{slug}.html")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"[DEBUG] HTML disimpan → {debug_path}")

    return BeautifulSoup(html, "lxml")


# ── Scrapers ───────────────────────────────────────────────────────────────────

def scrape_190():
    soup = fetch_and_parse(URL_WA_190, wait_for_selector="ha-wysiwyg")
    if not soup:
        return "", []
    return get_clean_text_190(soup), extract_service_fee_from_soup(soup)


def scrape_491():
    soup = fetch_and_parse(URL_WA_491, wait_for_selector="ha-visa-card")
    if not soup:
        return "", []
    return get_clean_text_491(soup), extract_service_fee_from_soup(soup)


# ── Main ───────────────────────────────────────────────────────────────────────

def scrape_wa():
    logger.info("=== Scraping WA Requirements ===")

    text_190, fees_190 = scrape_190()
    text_491, fees_491 = scrape_491()

    all_fees_190 = ", ".join(sorted(set(fees_190))) if fees_190 else "-"
    all_fees_491 = ", ".join(sorted(set(fees_491))) if fees_491 else "-"

    data = [
        {
            "state code": "WA",
            "state stream": "WA_190",
            "requirements": text_190,
            "service fee": all_fees_190,
        },
        {
            "state code": "WA",
            "state stream": "WA_491",
            "requirements": text_491,   # Main + Subsequent bullets digabung
            "service fee": all_fees_491,
        },
    ]

    return pd.DataFrame(data)


def export_results(df):
    export_dataframe(
        df,
        output_dir=_OUTPUT_DIR,
        filename_prefix="requirements_wa",
        preview_columns=["state code", "state stream", "service fee"],
    )


if __name__ == "__main__":
    final_df = scrape_wa()
    export_results(final_df)