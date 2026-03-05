import logging
import os
import re
import pandas as pd
from bs4 import BeautifulSoup

# ==========================
# LINK VIC
# ==========================
URL_VIC_190 = "https://liveinmelbourne.vic.gov.au/migrate/skilled-migration-visas/skilled-nominated-visa-subclass-190"
URL_VIC_491 = "https://liveinmelbourne.vic.gov.au/migrate/skilled-migration-visas/491" 
# ==========================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "vic")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_service_fee_from_soup(soup):
    """Scan all text for any service/application fee dollar amounts."""
    fees = []

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True).lower()
        if "service fee" in text or "application fee" in text:
            found = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)
            if found:
                fees.extend(found)

    return fees


def scrape_vic_190():
    """
    VIC Subclass 190 page uses an accordion structure.
    Each accordion item has:
      - Heading : element with class containing 'accordion__header'
      - Content : element with class containing 'accordion__body'

    Correct flow per accordion item:
      1. Click the header to expand it
      2. Wait for animation
      3. Snapshot DOM
      4. Extract the body content for THIS header only (by its index)
      5. Repeat for next header
    """
    logger.info(f"Fetching VIC 190 (accordion click mode): {URL_VIC_190}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright tidak terinstall.")
        return "", []

    all_lines = []
    all_fees = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL_VIC_190, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # Count total accordion headers upfront
        total = page.eval_on_selector_all(
            "[class*='accordion__header']",
            "els => els.length"
        )
        logger.info(f"Found {total} accordion headers")

        for i in range(total):
            # Re-query headers each iteration (DOM may shift after click)
            headers = page.query_selector_all("[class*='accordion__header']")
            if i >= len(headers):
                logger.warning(f"Header index {i} out of range, skipping")
                break

            header = headers[i]

            # --- 1. Get heading text BEFORE clicking ---
            heading_text = header.inner_text().strip()
            if not heading_text:
                continue

            logger.info(f"Clicking accordion [{i}]: {heading_text}")

            # --- 2. Click to expand ---
            header.click()
            page.wait_for_timeout(600)  # wait for CSS expand animation

            # --- 3. Snapshot DOM after this click ---
            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            # Collect fees from this snapshot
            all_fees.extend(extract_service_fee_from_soup(soup))

            all_lines.append(f"\n{heading_text.upper()}")

            # --- 4. Find the Nth accordion__body (same index as header) ---
            bodies = soup.find_all(
                lambda tag: tag.get("class") and
                any("accordion__body" in c for c in tag.get("class", []))
            )

            if i < len(bodies):
                body = bodies[i]

                # Walk body children in DOM order to preserve structure
                for el in body.find_all(["h2", "h3", "h4", "h5", "p", "ul"]):
                    tag = el.name

                    if tag in ("h2", "h3", "h4", "h5"):
                        text = el.get_text(" ", strip=True)
                        if text:
                            all_lines.append(f"  [{text}]")

                    elif tag == "p":
                        text = el.get_text(" ", strip=True)
                        if text:
                            all_lines.append(f"  {text}")

                    elif tag == "ul":
                        for li in el.find_all("li", recursive=False):
                            text = li.get_text(" ", strip=True)
                            if text:
                                all_lines.append(f"- {text}")
            else:
                logger.warning(f"No accordion__body at index {i} for: {heading_text}")

        browser.close()

    return "\n".join(all_lines).strip(), list(set(all_fees))


def scrape_vic_491():
    """
    VIC Subclass 491 page — same accordion structure as 190.
    Click each accordion__header, snapshot DOM, extract accordion__body at same index.
    """
    logger.info(f"Fetching VIC 491 (accordion click mode): {URL_VIC_491}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright tidak terinstall.")
        return "", []

    all_lines = []
    all_fees = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL_VIC_491, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        total = page.eval_on_selector_all(
            "[class*='accordion__header']",
            "els => els.length"
        )
        logger.info(f"Found {total} accordion headers")

        for i in range(total):
            headers = page.query_selector_all("[class*='accordion__header']")
            if i >= len(headers):
                logger.warning(f"Header index {i} out of range, skipping")
                break

            header = headers[i]
            heading_text = header.inner_text().strip()
            if not heading_text:
                continue

            logger.info(f"Clicking accordion [{i}]: {heading_text}")
            header.click()
            page.wait_for_timeout(600)

            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            all_fees.extend(extract_service_fee_from_soup(soup))
            all_lines.append(f"\n{heading_text.upper()}")

            bodies = soup.find_all(
                lambda tag: tag.get("class") and
                any("accordion__body" in c for c in tag.get("class", []))
            )

            if i < len(bodies):
                body = bodies[i]
                for el in body.find_all(["h2", "h3", "h4", "h5", "p", "ul"]):
                    tag = el.name
                    if tag in ("h2", "h3", "h4", "h5"):
                        text = el.get_text(" ", strip=True)
                        if text:
                            all_lines.append(f"  [{text}]")
                    elif tag == "p":
                        text = el.get_text(" ", strip=True)
                        if text:
                            all_lines.append(f"  {text}")
                    elif tag == "ul":
                        for li in el.find_all("li", recursive=False):
                            text = li.get_text(" ", strip=True)
                            if text:
                                all_lines.append(f"- {text}")
            else:
                logger.warning(f"No accordion__body at index {i} for: {heading_text}")

        browser.close()

    return "\n".join(all_lines).strip(), list(set(all_fees))


def scrape_vic():
    logger.info("=== Scraping VIC Requirements ===")

    vic_190_text, vic_190_fees = scrape_vic_190()
    vic_491_text, vic_491_fees = scrape_vic_491()

    all_fees = (vic_190_fees or []) + (vic_491_fees or [])
    service_fee_val = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    data = [
        {
            "state code": "VIC",
            "state stream": "Skilled_Nominated_Visa_Subclass_190",
            "requirements": vic_190_text,
            "service fee": service_fee_val,
        },
        {
            "state code": "VIC",
            "state stream": "Skilled_Work_Regional_Visa_Subclass_491",
            "requirements": vic_491_text,
            "service fee": service_fee_val,
        },
    ]

    return pd.DataFrame(data)


def export_results(df):
    if df is None or df.empty:
        logger.error("Data kosong.")
        return

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    json_path = os.path.join(_OUTPUT_DIR, "requirements_vic.json")
    df.to_json(json_path, orient="records", indent=4, force_ascii=False)

    csv_path = os.path.join(_OUTPUT_DIR, "requirements_vic.csv")
    try:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    except PermissionError:
        logger.warning(f"Tidak dapat menulis {csv_path}. Menulis ke fallback .tmp")
        try:
            df.to_csv(csv_path + ".tmp", index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.error(f"Gagal menulis CSV fallback: {e}")

    try:
        df.to_excel(os.path.join(_OUTPUT_DIR, "requirements_vic.xlsx"), index=False)
    except PermissionError:
        logger.warning("Tidak dapat menulis Excel (PermissionError), melewatkan xlsx.")
    except Exception as e:
        logger.error(f"Gagal menulis Excel: {e}")

    logger.info(f"Scraping selesai. File JSON disimpan di: {json_path}")

    print("\nPreview Data:")
    print(df[["state code", "state stream", "service fee"]])


if __name__ == "__main__":
    final_df = scrape_vic()
    export_results(final_df)