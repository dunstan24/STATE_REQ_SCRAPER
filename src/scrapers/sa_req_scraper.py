import logging
import os
import re
import pandas as pd
from bs4 import BeautifulSoup

# ==========================
# LINK SA
# ==========================
URL_SA_EMPLOYMENT = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/skilled-employment-in-south-australia"
URL_SA_GRADUATES = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/south-australian-graduates"
URL_SA_OUTER = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/outer-regional-skilled-employment"
URL_SA_OFFSHORE = "https://migration.sa.gov.au/before-applying/visa-options-and-pathways/skilled-migrants/moving-to-south-australia-from-overseas"
# ==========================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "sa")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_service_fee_from_soup(soup):

    fees = []

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True).lower()

        if "service fee" in text or "application fee" in text:

            found = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)

            if found:
                fees.extend(found)

    return fees


def get_clean_text(soup, url=None):
    """
    Extract SA requirements using correct structure.
    Different logic based on URL:
    - URL_SA_OUTER:    Find h2 "Eligibility guidelines", grab all li from subsequent t-copy sections
    - URL_SA_OFFSHORE: Find ALL h2 headings, grab all li from each subsequent t-copy section
    - Others:          Standard parsing (h2 + t-copy in same section)
    """

    lines = []

    skip_keywords = ["NOMINATION PROCESS", "SKILLED MIGRANTS", "GRADUATES WHO ACHIEVE", "INVITATIONS TO APPLY"]

    # ------------------------------------------------------------------ #
    # Special logic for Outer Regional (link 3)
    # ------------------------------------------------------------------ #
    if url and URL_SA_OUTER in url:
        all_h2 = soup.find_all("h2", class_="t-heading")
        target_heading = None

        for h2 in all_h2:
            if "Eligibility guidelines" in h2.get_text(strip=True):
                target_heading = h2
                break

        if target_heading:
            title = target_heading.get_text(strip=True)
            lines.append(f"\n{title.upper()}")

            parent_container = target_heading.find_parent("div", class_="l-grid-contained")

            if parent_container:
                next_container = parent_container.find_next_sibling("div", class_="l-grid-contained")

                if next_container:
                    t_copy_list = next_container.find_all("div", class_="t-copy")
                    for t_copy in t_copy_list:
                        for ul in t_copy.find_all("ul"):
                            for li in ul.find_all("li", recursive=False):
                                text = li.get_text(" ", strip=True)
                                if text:
                                    lines.append(f"- {text}")

        return "\n".join(lines).strip()

    # ------------------------------------------------------------------ #
    # Special logic for Offshore / Moving from Overseas (link 4)
    #
    # Page structure:
    #   LEFT  — heading buttons: div[data-tab-btn][id="N"]
    #                              > button > div > span.z-10  (heading text)
    #   RIGHT — content panels:  div[id="N"] containing div.t-copy
    #                             (hidden until heading is clicked;
    #                              visibility toggled via "parent-is-selected"
    #                              CSS class — Playwright must click each btn)
    #
    # Because content panels share the same numeric id as their heading
    # button we match them by id after clicking each button.
    # NOTE: soup must have been built AFTER clicking (see scrape_offshore).
    # ------------------------------------------------------------------ #
    if url and URL_SA_OFFSHORE in url:
        # All heading buttons, ordered by their numeric id
        heading_divs = soup.find_all("div", attrs={"data-tab-btn": True})

        for heading_div in heading_divs:
            tab_id = heading_div.get("id")  # "0", "1", "2", ...

            # Extract heading text from <span class="z-10">
            span = heading_div.find("span", class_="z-10")
            if not span:
                continue
            heading_text = span.get_text(strip=True)
            if not heading_text:
                continue

            lines.append(f"\n{heading_text.upper()}")

            # Find the matching content panel by id (same numeric id,
            # but this div does NOT have data-tab-btn — distinguish by
            # checking for t-copy inside)
            # There may be multiple divs with the same id; we want the
            # one that contains a t-copy (the content panel).
            content_candidates = soup.find_all("div", id=tab_id)
            for candidate in content_candidates:
                # Skip the heading button div itself
                if candidate.has_attr("data-tab-btn"):
                    continue

                t_copy_list = candidate.find_all("div", class_="t-copy")
                for t_copy in t_copy_list:
                    # Paragraph context lines
                    for p in t_copy.find_all("p"):
                        text = p.get_text(" ", strip=True)
                        if text:
                            lines.append(f"  {text}")

                    # Bullet-point requirements
                    for ul in t_copy.find_all("ul"):
                        for li in ul.find_all("li", recursive=False):
                            text = li.get_text(" ", strip=True)
                            if text:
                                lines.append(f"- {text}")

        return "\n".join(lines).strip()

    # ------------------------------------------------------------------ #
    # Standard logic for Employment and Graduates
    # ------------------------------------------------------------------ #
    sections = soup.find_all("div", class_="col-span-full")

    current_heading = None

    for section in sections:

        title_tag = section.find("h2", class_="t-heading")

        if title_tag:
            title = title_tag.get_text(strip=True)

            if any(skip in title.upper() for skip in skip_keywords):
                continue

            current_heading = title
            lines.append(f"\n{title.upper()}")

        content = section.find("div", class_="t-copy")

        if content and current_heading:
            for li in content.find_all("li"):
                text = li.get_text(" ", strip=True)

                if text:
                    lines.append(f"- {text}")

    return "\n".join(lines).strip()


def scrape_offshore():
    """
    Offshore page uses a JS tab panel — content is only visible after
    clicking each heading button.  We use Playwright directly to:
      1. Load the page
      2. Find all heading buttons: div[data-tab-btn] > button
      3. Click each one, wait for CSS transition, snapshot DOM
      4. Extract heading text + matching content panel by numeric id
    """
    logger.info(f"Fetching offshore (tab-click mode): {URL_SA_OFFSHORE}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright tidak terinstall.")
        return "", []

    all_lines = []
    fees = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL_SA_OFFSHORE, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # Collect all heading buttons in DOM order
        tab_buttons = page.query_selector_all("div[data-tab-btn] button")

        for btn in tab_buttons:
            # Get heading text from <span class="z-10"> inside the button
            span = btn.query_selector("span.z-10")
            if not span:
                continue
            heading_text = span.inner_text().strip()
            if not heading_text:
                continue

            # Click to activate the tab panel
            btn.click()
            page.wait_for_timeout(600)  # buffer for 300ms CSS transition

            # Get numeric id from the parent div[data-tab-btn]
            tab_id = btn.evaluate("el => el.closest('[data-tab-btn]').getAttribute('id')")

            # Snapshot DOM after click
            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            # Collect any fees visible in this panel state
            fees.extend(extract_service_fee_from_soup(soup))

            all_lines.append(f"\n{heading_text.upper()}")

            # Match content panel: same numeric id, no data-tab-btn attribute
            for candidate in soup.find_all("div", id=tab_id):
                if candidate.has_attr("data-tab-btn"):
                    continue  # skip the heading div itself
                for t_copy in candidate.find_all("div", class_="t-copy"):
                    for p in t_copy.find_all("p"):
                        text = p.get_text(" ", strip=True)
                        if text:
                            all_lines.append(f"  {text}")
                    for ul in t_copy.find_all("ul"):
                        for li in ul.find_all("li", recursive=False):
                            text = li.get_text(" ", strip=True)
                            if text:
                                all_lines.append(f"- {text}")

        browser.close()

    return "\n".join(all_lines).strip(), list(set(fees))


def fetch_and_parse(url):

    logger.info(f"Fetching: {url}")

    try:
        try:
            from playwright_helper import get_page_source_playwright
        except ImportError:
            from src.scrapers.playwright_helper import get_page_source_playwright

        html = get_page_source_playwright(
            url=url,
            wait_for_selector="body",
            extra_wait_seconds=3,
            bypass_cf=False,
        )

    except ImportError:
        logger.error("playwright_helper tidak ditemukan.")
        return None

    if not html:
        logger.error("HTML tidak didapat.")
        return None

    return BeautifulSoup(html, "lxml")


def scrape_page(url):

    soup = fetch_and_parse(url)

    if not soup:
        return "", []

    text = get_clean_text(soup, url)

    fees = extract_service_fee_from_soup(soup)

    return text, fees


def scrape_sa(url=None):

    logger.info("=== Scraping SA Requirements ===")

    employment_text, employment_fees = scrape_page(URL_SA_EMPLOYMENT)
    graduates_text, graduates_fees = scrape_page(URL_SA_GRADUATES)
    outer_text, outer_fees = scrape_page(URL_SA_OUTER)
    offshore_text, offshore_fees = scrape_offshore()  # ← uses Playwright tab-click

    # Combine all fees across all four streams
    all_fees = (
        (employment_fees or [])
        + (graduates_fees or [])
        + (outer_fees or [])
        + (offshore_fees or [])   # ← NEW
    )
    service_fee_val = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    data = [
        {
            "state code": "SA",
            "state stream": "Skilled_Employment_in_South_Australia",
            "requirements": employment_text,
            "service fee": service_fee_val,
        },
        {
            "state code": "SA",
            "state stream": "South_Australian_Graduates",
            "requirements": graduates_text,
            "service fee": service_fee_val,
        },
        {
            "state code": "SA",
            "state stream": "Outer_Regional_Skilled_Employment",
            "requirements": outer_text,
            "service fee": service_fee_val,
        },
        {
            "state code": "SA",
            "state stream": "Moving_to_South_Australia_from_Overseas",  # ← NEW
            "requirements": offshore_text,
            "service fee": service_fee_val,
        },
    ]

    return pd.DataFrame(data)


def export_results(df):

    if df is None or df.empty:

        logger.error("Data kosong.")
        return

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    json_path = os.path.join(_OUTPUT_DIR, "requirements_sa.json")

    df.to_json(
        json_path,
        orient="records",
        indent=4,
        force_ascii=False
    )

    csv_path = os.path.join(_OUTPUT_DIR, "requirements_sa.csv")
    try:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    except PermissionError:
        logger.warning(f"Tidak dapat menulis {csv_path} (PermissionError). Menulis ke {csv_path}.tmp sebagai fallback.")
        try:
            df.to_csv(csv_path + ".tmp", index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.error(f"Gagal menulis CSV fallback: {e}")

    try:
        df.to_excel(os.path.join(_OUTPUT_DIR, "requirements_sa.xlsx"), index=False)
    except PermissionError:
        logger.warning("Tidak dapat menulis Excel output (PermissionError), melewatkan penulisan xlsx.")
    except Exception as e:
        logger.error(f"Gagal menulis Excel: {e}")

    logger.info(f"Scraping selesai. File JSON disimpan di: {json_path}")

    print("\nPreview Data:")
    print(df[["state code", "state stream", "service fee"]])


if __name__ == "__main__":

    final_df = scrape_sa()
    export_results(final_df)