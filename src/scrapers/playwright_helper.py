"""
playwright_helper.py — Single fetch engine untuk semua state scraper.

Dua mode operasi:
  - bypass_cf=False (default) : headless biasa (Playwright), untuk state tanpa proteksi CF
  - bypass_cf=True            : headless CF-safe (Camoufox), khusus ACT (Cloudflare Turnstile)

Instalasi (jalankan sekali):
    pip install playwright camoufox[geoip]
    playwright install chromium
    python -m camoufox fetch
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ── Cek dependensi ─────────────────────────────────────────────────────────────

try:
    from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    logger.error(
        "[Playwright] 'playwright' belum diinstall.\n"
        "Jalankan: pip install playwright && playwright install chromium"
    )

try:
    from camoufox.async_api import AsyncCamoufox
    _CAMOUFOX_AVAILABLE = True
except ImportError:
    _CAMOUFOX_AVAILABLE = False
    logger.warning(
        "[Camoufox] 'camoufox' belum diinstall.\n"
        "Jalankan: pip install camoufox[geoip] && python -m camoufox fetch\n"
        "bypass_cf=True tidak akan berfungsi tanpa camoufox."
    )


# ── Konstanta ──────────────────────────────────────────────────────────────────

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_CLOUDFLARE_MARKERS = (
    "just a moment", "cloudflare", "security verification",
    "performing security", "enable javascript and cookies",
    "ray id:",
)

# Timeout dalam milidetik
_CF_TURNSTILE_TIMEOUT_MS  = 60_000   # 60s — tunggu Turnstile auto-resolve
_PAGE_LOAD_TIMEOUT_MS     = 90_000   # 90s — max load halaman (CF mode)
_SELECTOR_WAIT_MS         = 30_000   # 30s — tunggu selector muncul
_HEADLESS_LOAD_TIMEOUT_MS = 30_000   # 30s — cukup untuk non-CF sites


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_cloudflare_page(html: str) -> bool:
    if not html:
        return False
    snippet = html[:3000].lower()
    return any(marker in snippet for marker in _CLOUDFLARE_MARKERS)


async def _wait_for_turnstile(page, timeout_ms: int = _CF_TURNSTILE_TIMEOUT_MS) -> bool:
    """Poll sampai halaman CF challenge hilang. Return True jika berhasil."""
    logger.info("[Camoufox] Menunggu Cloudflare Turnstile selesai...")
    start    = time.time()
    deadline = timeout_ms / 1000

    while (time.time() - start) < deadline:
        try:
            if not _is_cloudflare_page(await page.content()):
                logger.info(f"[Camoufox] Turnstile resolved dalam {time.time()-start:.1f}s")
                return True
        except Exception:
            pass
        await asyncio.sleep(2)

    logger.warning(f"[Camoufox] Turnstile TIMEOUT setelah {deadline:.0f}s")
    return False


# ── Core async fetchers ────────────────────────────────────────────────────────

async def _fetch_with_camoufox(
    url: str,
    wait_for_selector: Optional[str],
    extra_wait_seconds: int,
) -> Optional[str]:
    """Fetch menggunakan Camoufox — headless, bypass Cloudflare Turnstile."""
    if not _CAMOUFOX_AVAILABLE:
        logger.error(
            "[Camoufox] Module tidak tersedia. "
            "Jalankan: pip install camoufox[geoip] && python -m camoufox fetch"
        )
        return None

    try:
        async with AsyncCamoufox(
            headless=True,
            geoip=True,
            locale="en-AU",
            os="windows",
        ) as browser:
            page = await browser.new_page()

            logger.info(f"[Camoufox] Membuka: {url}")
            await page.goto(url, timeout=_PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")

            # Tunggu sampai CF challenge selesai jika ada
            if _is_cloudflare_page(await page.content()):
                logger.info("[Camoufox] CF challenge terdeteksi, menunggu auto-resolve...")
                resolved = await _wait_for_turnstile(page)
                if not resolved:
                    logger.error("[Camoufox] Gagal melewati Cloudflare Turnstile.")
                    with open("debug_cf_blocked.html", "w", encoding="utf-8") as f:
                        f.write(await page.content())
                    return None

            # Tunggu selector konten muncul
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=_SELECTOR_WAIT_MS)
                    logger.info(f"[Camoufox] Selector '{wait_for_selector}' ditemukan.")
                except Exception:
                    logger.warning(
                        f"[Camoufox] Selector '{wait_for_selector}' tidak muncul "
                        f"dalam {_SELECTOR_WAIT_MS/1000:.0f}s — lanjut ambil HTML."
                    )

            if extra_wait_seconds > 0:
                await asyncio.sleep(extra_wait_seconds)

            html = await page.content()
            logger.info(f"[Camoufox] HTML didapat ({len(html):,} chars)")
            return html

    except Exception as e:
        logger.error(f"[Camoufox] Error: {e}", exc_info=True)
        return None


async def _fetch_with_playwright(
    url: str,
    wait_for_selector: Optional[str],
    extra_wait_seconds: int,
) -> Optional[str]:
    """Fetch menggunakan Playwright headless biasa — untuk site tanpa CF."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=_UA,
            locale="en-AU",
            timezone_id="Australia/Sydney",
        )
        page = await context.new_page()

        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
        })

        try:
            logger.info(f"[Playwright] Membuka: {url}")
            await page.goto(url, timeout=_HEADLESS_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")

            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=_SELECTOR_WAIT_MS)
                    logger.info(f"[Playwright] Selector '{wait_for_selector}' ditemukan.")
                except PWTimeout:
                    logger.warning(
                        f"[Playwright] Selector '{wait_for_selector}' tidak muncul "
                        f"dalam {_SELECTOR_WAIT_MS/1000:.0f}s — lanjut ambil HTML."
                    )

            if extra_wait_seconds > 0:
                await asyncio.sleep(extra_wait_seconds)

            html = await page.content()
            logger.info(f"[Playwright] HTML didapat ({len(html):,} chars)")
            return html

        except Exception as e:
            logger.error(f"[Playwright] Error: {e}", exc_info=True)
            return None
        finally:
            await browser.close()


async def _fetch_async(
    url: str,
    bypass_cf: bool,
    wait_for_selector: Optional[str],
    extra_wait_seconds: int,
) -> Optional[str]:
    """Router: pilih engine berdasarkan bypass_cf flag."""
    if bypass_cf:
        return await _fetch_with_camoufox(url, wait_for_selector, extra_wait_seconds)
    else:
        return await _fetch_with_playwright(url, wait_for_selector, extra_wait_seconds)


# ── Public API ─────────────────────────────────────────────────────────────────

# Konstanta publik — bisa diimport scraper lain yang butuh nilai timeout
PAGE_LOAD_TIMEOUT_MS = _HEADLESS_LOAD_TIMEOUT_MS   # 30s, untuk non-CF sites
SELECTOR_TIMEOUT_MS  = _SELECTOR_WAIT_MS            # 30s, tunggu selector


def get_page_source_playwright(
    url: str,
    wait_for_selector: Optional[str] = "table",
    extra_wait_seconds: int = 3,
    bypass_cf: bool = False,
) -> Optional[str]:
    """
    Synchronous entry point — dipanggil dari semua state scraper.

    Parameters
    ----------
    url               : URL yang akan di-fetch.
    wait_for_selector : CSS selector yang ditunggu sebelum ambil HTML.
                        Default 'table'. Set None jika tidak perlu tunggu.
    extra_wait_seconds: Detik tambahan setelah selector muncul (render JS).
    bypass_cf         : False (default) → headless Playwright untuk state normal.
                        True  → headless Camoufox khusus ACT (Cloudflare Turnstile).

    Returns
    -------
    HTML string atau None jika gagal.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        logger.error("[Playwright] Module tidak tersedia.")
        return None

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _fetch_async(url, bypass_cf, wait_for_selector, extra_wait_seconds)
        )
    except Exception as e:
        logger.error(f"[Playwright] Gagal menjalankan event loop: {e}", exc_info=True)
        return None
    finally:
        loop.close()


async def create_browser_context(bypass_cf: bool = False):
    """
    Buat dan return resource browser yang sudah dikonfigurasi.

    Digunakan oleh scraper yang butuh interaksi custom di dalam page
    (contoh: WA scraper yang perlu klik Show All + tunggu AJAX).

    ┌─────────────────┬──────────────────────────────────────────────────┐
    │ bypass_cf=False │ returns (playwright_instance, browser, context)  │
    │ bypass_cf=True  │ returns (camoufox_instance, browser, None)       │
    └─────────────────┴──────────────────────────────────────────────────┘

    PENTING: Caller wajib menutup resource setelah selesai.

    Contoh bypass_cf=False (Playwright):
        pw, browser, context = await create_browser_context()
        try:
            page = await context.new_page()
            html = await page.content()
        finally:
            await browser.close()
            await pw.stop()

    Contoh bypass_cf=True (Camoufox):
        cf, browser, _ = await create_browser_context(bypass_cf=True)
        try:
            page = await browser.new_page()
            html = await page.content()
        finally:
            await browser.close()
            await cf.__aexit__(None, None, None)

    Parameters
    ----------
    bypass_cf : False → headless Playwright.
                True  → headless Camoufox (CF-safe).

    Returns
    -------
    Tuple (engine_instance, browser, context_or_None)
    """
    if bypass_cf:
        if not _CAMOUFOX_AVAILABLE:
            raise RuntimeError(
                "camoufox tidak tersedia. "
                "Jalankan: pip install camoufox[geoip] && python -m camoufox fetch"
            )
        cf      = AsyncCamoufox(headless=True, geoip=True, locale="en-AU", os="windows")
        browser = await cf.__aenter__()
        return cf, browser, None

    else:
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "playwright tidak tersedia. "
                "Jalankan: pip install playwright && playwright install chromium"
            )
        from playwright.async_api import async_playwright as _async_playwright
        pw      = await _async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(user_agent=_UA, locale="en-AU", timezone_id="Australia/Sydney")
        return pw, browser, context