



import logging
import os
import re
import pandas as pd
from bs4 import BeautifulSoup

# ==========================
# LINK QLD
# ==========================
URL_QLD = "https://migration.qld.gov.au/visa-options/skilled-visas/skilled-workers-living-in-queensland"
URL_QLD_OUTSIDE="https://migration.qld.gov.au/visa-options/skilled-visas/skilled-workers-living-offshore"
# ==========================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "qld")

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


def get_clean_text(soup):
    """Fungsi umum untuk ekstraksi requirements.

    Untuk halaman QLD tertentu kita ingin memproses tabel yang berisi
    persyaratan. Logik ini juga bisa dipakai di negara lain bila terdapa
    tabel serupa.

    - Setiap baris tabel dianggap item baru.
    - Sel kolom pertama menjadi judul/baris atas.
    - Isi kolom kedua dipecah ke dalam paragraf/"li" lalu diberi bullet.
    """

    container = soup.find("div", id=lambda x: x and x.startswith("component_"))

    if not container:
        container = soup.find("body")
    # --- Remove common non-content blocks that often contain navigation/menu/footer
    # This helps avoid scraping site chrome (lots of repeated nav text) while
    # keeping the main document content intact. We target semantic elements and
    # classes/ids commonly used for navigation.
    for bad in container.find_all(["nav", "header", "footer", "aside"]):
        bad.decompose()

    # also remove elements whose class or id looks like navigation/menu/breadcrumb
    nav_like = re.compile(r"nav|menu|breadcrumb|masthead|site-header|site-footer|skip|primary", re.I)
    for el in container.find_all(True):
        # some parsed nodes may have unusual attrs; guard defensively
        attrs = getattr(el, 'attrs', None)
        if not attrs:
            continue

        classes = attrs.get("class") or []
        el_id = attrs.get("id", "") or ""

        # if any class or id looks like navigation/menu/breadcrumb, remove element
        try:
            if any(nav_like.search(c) for c in classes) or nav_like.search(el_id):
                el.decompose()
        except Exception:
            # be conservative: skip problematic elements rather than crash
            continue

    # --- cek tabel terlebih dahulu ---
    table_lines = []
    tbodies = container.find_all("tbody")
    for tbody in tbodies:
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue

            # kolom pertama dijadikan judul/heading
            header = cells[0].get_text(strip=True)
            if header:
                table_lines.append(header)

            # kolom kedua dan seterusnya diproses jadi bullet
            if len(cells) > 1:
                cell = cells[1]
                # periksa teks luar tag (misalnya teks sebelum <p>)
                leading = []
                for child in cell.contents:
                    if getattr(child, 'name', None) in ("p", "li"):
                        break
                    if getattr(child, 'string', None) and child.string.strip():
                        leading.append(child.string.strip())
                if leading:
                    table_lines.append(f"- {' '.join(leading)}")

                # ambil p dan li saja, urutan sesuai dom
                for tag in cell.find_all(["p", "li"]):
                    text = tag.get_text(" ", strip=True)
                    if not text:
                        continue
                    table_lines.append(f"- {text}")
        # remove tbody to avoid double-processing but we will prefer table-only output
        tbody.decompose()

    # If we found any tbody content, return only that (user requested to not include other page chrome)
    if table_lines:
        return "\n".join(table_lines).strip()

    lines = []

    for tag in container.find_all(["p", "li", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if not text:
            continue

        if tag.name == "li":
            lines.append(f"• {text}")
        elif tag.name in ["h2", "h3"]:
            lines.append(f"\n{text.upper()}\n")
        else:
            lines.append(text)

    result = "\n".join(lines).strip()

    if table_lines:
        table_section = "\n".join(table_lines).strip()
        # letakkan bagian tabel di awal supaya struktur logika terlihat jelas
        return table_section + ("\n\n" + result if result else "")

    return result


def fetch_and_parse(url):

    logger.info(f"Fetching: {url}")

    try:
        try:
            # prefer local import when running as module inside package
            from playwright_helper import get_page_source_playwright
        except ImportError:
            # fallback to package import when running from repo root
            from src.scrapers.playwright_helper import get_page_source_playwright

        # QLD page doesn't use Cloudflare turnstile. headless mode is faster
        # and avoids the unnecessary 60‑second wait when the old CF detector
        # misfired.
        html = get_page_source_playwright(
            url=url,
            wait_for_selector="body",
            extra_wait_seconds=3,
            bypass_cf=False,   # no CF protection on QLD site
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

    text = get_clean_text(soup)

    fees = extract_service_fee_from_soup(soup)

    return text, fees


def scrape_qld():

    logger.info("=== Scraping QLD Requirements ===")
    # Scrape onshore page
    qld_text_onshore, qld_fees_onshore = scrape_page(URL_QLD)

    # Scrape offshore page (new link provided by user)
    qld_text_offshore, qld_fees_offshore = scrape_page(URL_QLD_OUTSIDE)

    # combine fees from both pages
    all_fees = (qld_fees_onshore or []) + (qld_fees_offshore or [])
    service_fee_val = ", ".join(sorted(set(all_fees))) if all_fees else "-"

    data = [
        {
            "state code": "QLD",
            "state stream": "Workers_Living_in_Queensland",
            "requirements": qld_text_onshore,
            "service fee": service_fee_val,
        },
        {
            "state code": "QLD",
            "state stream": "Workers_Living_offshore",
            "requirements": qld_text_offshore,
            "service fee": service_fee_val,
        }
    ]

    return pd.DataFrame(data)


def export_results(df):

    if df is None or df.empty:

        logger.error("Data kosong.")
        return

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    # JSON
    json_path = os.path.join(_OUTPUT_DIR, "requirements_qld.json")

    df.to_json(
        json_path,
        orient="records",
        indent=4,
        force_ascii=False
    )

    # CSV
    csv_path = os.path.join(_OUTPUT_DIR, "requirements_qld.csv")
    try:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    except PermissionError:
        logger.warning(f"Tidak dapat menulis {csv_path} (PermissionError). Menulis ke {csv_path}.tmp sebagai fallback.")
        try:
            df.to_csv(csv_path + ".tmp", index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.error(f"Gagal menulis CSV fallback: {e}")

    # Excel
    try:
        df.to_excel(os.path.join(_OUTPUT_DIR, "requirements_qld.xlsx"), index=False)
    except PermissionError:
        logger.warning("Tidak dapat menulis Excel output (PermissionError), melewatkan penulisan xlsx.")
    except Exception as e:
        logger.error(f"Gagal menulis Excel: {e}")

    logger.info(f"Scraping selesai. File JSON disimpan di: {json_path}")

    print("\nPreview Data:")
    print(df[["state code", "state stream", "service fee"]])


if __name__ == "__main__":

    final_df = scrape_qld()

    export_results(final_df)