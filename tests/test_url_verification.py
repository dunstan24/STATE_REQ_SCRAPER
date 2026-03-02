"""
URL Verification Tests
======================
Menguji aksesibilitas semua URL di config.TARGET_URLS dan WA CSV endpoint.
Memerlukan koneksi internet aktif.

Jalankan dengan:
    pytest tests/test_url_verification.py -v

Atau hanya URL check:
    pytest tests/test_url_verification.py -v -m url_check

Catatan status khusus:
  - 403 dari situs pemerintah = normal (anti-bot), URL valid, scraper pakai Selenium
  - WA CSV endpoint butuh session cookie dari browser — tidak bisa dicek via requests
"""

import sys
import os
import time
import requests
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import TARGET_URLS
from src.scrapers.wa_scraper import CSV_ENDPOINT

# ── Konstanta ──────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT  = 20      # detik
MAX_RETRIES      = 2       # coba ulang jika timeout
RETRY_DELAY      = 3       # detik antar retry
VALID_STATUS_MAX = 399     # status <= 399 dianggap OK (200, 301, 302, ...)

# Situs-situs yang diketahui memblokir requests biasa (anti-bot / Cloudflare).
# Scraper untuk situs ini sudah menggunakan Selenium — 403 via requests adalah NORMAL.
BOT_PROTECTED_STATES = {"ACT", "NT"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ── Helper ─────────────────────────────────────────────────────────────────────

def check_url(url: str) -> dict:
    """
    Coba akses URL dan kembalikan dict hasil:
      - status_code : int atau None
      - final_url   : URL setelah redirect
      - reachable   : bool
      - error       : pesan error jika gagal
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            return {
                "status_code": resp.status_code,
                "final_url":   resp.url,
                "reachable":   resp.status_code <= VALID_STATUS_MAX,
                "error":       None,
            }
        except requests.exceptions.SSLError as e:
            # Beberapa situs gov menggunakan sertifikat yg ketat; coba tanpa verify
            try:
                resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
                                    allow_redirects=True, verify=False)
                return {
                    "status_code": resp.status_code,
                    "final_url":   resp.url,
                    "reachable":   resp.status_code <= VALID_STATUS_MAX,
                    "error":       f"SSL warning (ignored): {e}",
                }
            except Exception as inner_e:
                error_msg = str(inner_e)
        except requests.exceptions.Timeout:
            error_msg = f"Timeout setelah {REQUEST_TIMEOUT}s (attempt {attempt}/{MAX_RETRIES})"
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"ConnectionError: {e}"
            break
        except Exception as e:
            error_msg = f"Exception: {type(e).__name__}: {e}"
            break

    return {"status_code": None, "final_url": url, "reachable": False, "error": error_msg}


# ── Fixtures / parameterize setup ──────────────────────────────────────────────

def _url_test_id(entry):
    """ID test yang mudah dibaca: STATE-listtype."""
    return f"{entry['state']}-{entry['list_type']}"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: TARGET_URLS dari config.py
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.url_check
@pytest.mark.parametrize("entry", TARGET_URLS, ids=_url_test_id)
def test_target_url_reachable(entry):
    """
    Setiap URL di config.TARGET_URLS harus dapat diakses
    (HTTP status 200-399, termasuk redirect).

    Khusus situs yang diketahui memblokir requests (ACT, NT):
    - Jika 403 → xfail: URL valid tapi bot-protected, scraper pakai Selenium.
    - Jika error lain (404, connection error) → FAIL tetap (URL mungkin mati).
    """
    url   = entry["url"]
    state = entry["state"]
    ltype = entry["list_type"]

    result = check_url(url)

    # Print detail untuk laporan test
    print(f"\n[{state}/{ltype}] {url}")
    print(f"  → Status  : {result['status_code']}")
    print(f"  → Final   : {result['final_url']}")
    if result["error"]:
        print(f"  → Warning : {result['error']}")

    # Jika situs ini diketahui bot-protected DAN hasilnya 403 → xfail
    if state in BOT_PROTECTED_STATES and result["status_code"] == 403:
        pytest.xfail(
            f"[{state}/{ltype}] Mengembalikan 403 Forbidden — "
            "situs ini memblokir requests biasa (anti-bot/Cloudflare). "
            "Scraper sudah menggunakan Selenium untuk mengakses halaman ini. "
            f"URL: {url}"
        )

    assert result["reachable"], (
        f"[{state}/{ltype}] URL tidak dapat diakses!\n"
        f"  URL    : {url}\n"
        f"  Status : {result['status_code']}\n"
        f"  Error  : {result['error']}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: WA CSV Endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.url_check
def test_wa_csv_endpoint_reachable():
    """WA CSV endpoint harus bisa diakses dan content-type mengandung csv atau text."""
    result = check_url(CSV_ENDPOINT)

    print(f"\n[WA] CSV Endpoint: {CSV_ENDPOINT}")
    print(f"  → Status : {result['status_code']}")
    print(f"  → Final  : {result['final_url']}")
    if result["error"]:
        print(f"  → Warning: {result['error']}")

    assert result["reachable"], (
        f"WA CSV endpoint tidak dapat diakses!\n"
        f"  URL    : {CSV_ENDPOINT}\n"
        f"  Status : {result['status_code']}\n"
        f"  Error  : {result['error']}"
    )


@pytest.mark.url_check
def test_wa_csv_endpoint_returns_csv_content():
    """
    WA CSV endpoint memerlukan session cookie dari browser (halaman utama WA)
    sebelum bisa mendownload CSV.

    Test ini di-skip secara otomatis karena:
    - Endpoint hanya bisa diakses via Selenium yang sudah punya session aktif
    - Download CSV langsung via requests.get() akan mengembalikan body kosong
    - Gunakan wa_scraper._scrape_via_csv() yang sudah handle skenario ini
    """
    pytest.skip(
        "WA CSV endpoint memerlukan session cookie dari browser. "
        "Tidak bisa diakses langsung via requests.get(). "
        "Gunakan Selenium melalui wa_scraper._scrape_via_csv() untuk download CSV. "
        f"Endpoint: {CSV_ENDPOINT}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: URL Summary Report (helper test yang tidak fail)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.url_check
def test_all_urls_summary(capsys):
    """
    Cetak ringkasan status semua URL sekaligus.
    Test ini SELALU PASS — berfungsi sebagai laporan ringkasan.
    """
    all_entries = TARGET_URLS + [{"state": "WA", "list_type": "csv-endpoint", "url": CSV_ENDPOINT}]

    results = []
    for entry in all_entries:
        r = check_url(entry["url"])
        state = entry["state"]
        bot_protected = state in BOT_PROTECTED_STATES and r["status_code"] == 403
        results.append({
            "state":         state,
            "type":          entry["list_type"],
            "url":           entry["url"],
            "bot_protected": bot_protected,
            **r,
        })

    print("\n" + "=" * 90)
    print("  RINGKASAN VERIFIKASI URL")
    print("=" * 90)
    print(f"  {'STATE':<6} {'TYPE':<15} {'STATUS':<8} {'RESULT':<18} URL")
    print("-" * 90)

    ok_count           = 0
    bot_protected_count = 0
    fail_count         = 0
    skip_count         = 0

    for r in results:
        status_str = str(r["status_code"]) if r["status_code"] else "ERR"
        if r["type"] == "csv-endpoint":
            result_str = "⏭️  SKIP (session)"
            skip_count += 1
        elif r["bot_protected"]:
            result_str = "⚠️  XFAIL (bot-lock)"
            bot_protected_count += 1
        elif r["reachable"]:
            result_str = "✅ OK"
            ok_count += 1
        else:
            result_str = "❌ FAIL"
            fail_count += 1
        print(f"  {r['state']:<6} {r['type']:<15} {status_str:<8} {result_str:<18} {r['url']}")

    print("=" * 90)
    print(
        f"  TOTAL: {len(results)} URL | "
        f"✅ OK: {ok_count} | "
        f"⚠️  Bot-Protected (xfail): {bot_protected_count} | "
        f"⏭️  Skipped: {skip_count} | "
        f"❌ FAIL: {fail_count}"
    )
    if bot_protected_count:
        print("  ℹ️  Bot-Protected = URL valid, scraper pakai Selenium (bukan requests biasa)")
    if skip_count:
        print("  ℹ️  Skipped = Endpoint butuh session cookie browser, tidak bisa dicek via requests")
    print("=" * 90)

    # Test ini selalu pass — hanya laporan
    assert True
