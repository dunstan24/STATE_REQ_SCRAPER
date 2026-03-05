"""
Script debug untuk inspeksi struktur accordion halaman TBO.
Jalankan ini lalu paste hasilnya untuk analisis.
"""

from bs4 import BeautifulSoup
from playwright_helper import get_page_source_playwright

TBO_URL = "https://example.gov.au/migration/pathway/tbo"  # ganti URL asli

html = get_page_source_playwright(
    url=TBO_URL,
    wait_for_selector="body",
    extra_wait_seconds=3,
    bypass_cf=False,
)

soup = BeautifulSoup(html, "lxml")

# ── 1. Berapa banyak div#content-accordion yang ditemukan? ───────────────────
accordions = soup.find_all(
    "div", {"class": "accordion accordion-flush", "id": "content-accordion"}
)
print(f"\n[1] Jumlah div#content-accordion ditemukan: {len(accordions)}")

# ── 2. Tiap accordion: berapa accordion-item dan apa teks button-nya? ─────────
for a_idx, acc in enumerate(accordions):
    items = acc.find_all("div", class_="accordion-item")
    print(f"\n[2] Accordion[{a_idx}] → {len(items)} accordion-item")
    for i_idx, item in enumerate(items):
        btn = item.find("button", class_="accordion-button")
        btn_text = btn.get_text(strip=True) if btn else "(no button)"
        body = item.find("div", class_="accordion-body")
        body_len = len(body.get_text(strip=True)) if body else 0
        print(
            f"     Item[{i_idx}] button: '{btn_text}' | accordion-body chars: {body_len}"
        )

# ── 3. Cek apakah accordion-body kosong atau None ────────────────────────────
print("\n[3] Detail accordion-body per item di accordion pertama:")
if accordions:
    first_acc = accordions[0]
    for i_idx, item in enumerate(first_acc.find_all("div", class_="accordion-item")):
        body = item.find("div", class_="accordion-body")
        if body:
            print(
                f"     Item[{i_idx}] body found, panjang teks: {len(body.get_text(strip=True))}"
            )
            print(f"     Preview: {body.get_text(strip=True)[:100]!r}")
        else:
            print(f"     Item[{i_idx}] body: TIDAK DITEMUKAN")
