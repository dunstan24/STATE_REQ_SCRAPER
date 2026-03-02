"""
playwright_helper.py — Single fetch engine untuk semua state scraper.

Dua mode operasi:
  - bypass_cf=False (default) : headless biasa, untuk 7 state tanpa proteksi CF
  - bypass_cf=True            : non-headless + stealth, khusus ACT (Cloudflare Turnstile)

Instalasi (jalankan sekali):
    pip install playwright playwright-stealth
    playwright install chromium
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
    from playwright_stealth import stealth_async
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False
    logger.warning(
        "[Playwright] 'playwright-stealth' belum diinstall.\n"
        "Jalankan: pip install playwright-stealth"
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


async def _wait_for_turnstile(page: "Page", timeout_ms: int = _CF_TURNSTILE_TIMEOUT_MS) -> bool:
    """Poll sampai halaman CF challenge hilang. Return True jika berhasil."""
    logger.info("[Playwright] Menunggu Cloudflare Turnstile selesai...")
    start    = time.time()
    deadline = timeout_ms / 1000

    while (time.time() - start) < deadline:
        try:
            if not _is_cloudflare_page(await page.content()):
                logger.info(f"[Playwright] Turnstile resolved dalam {time.time()-start:.1f}s")
                return True
        except Exception:
            pass
        await asyncio.sleep(2)

    logger.warning(f"[Playwright] Turnstile TIMEOUT setelah {deadline:.0f}s")
    return False


# ── Browser & context builders ─────────────────────────────────────────────────

async def _build_browser(playwright, bypass_cf: bool):
    """
    bypass_cf=True  → non-headless, window di luar layar, untuk Cloudflare.
    bypass_cf=False → headless standar, lebih cepat, untuk site biasa.
    """
    common_args = [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
    ]

    if bypass_cf:
        return await playwright.chromium.launch(
            headless=False,
            args=common_args + [
                "--window-position=-10000,0",
                "--window-size=1920,1080",
                "--disable-infobars",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
            ],
        )
    else:
        return await playwright.chromium.launch(
            headless=True,
            args=common_args,
        )


async def _build_context(browser, bypass_cf: bool):
    """Buat browser context dengan fingerprint yang tepat sesuai mode."""
    if bypass_cf:
        context = await browser.new_context(
            user_agent=_UA,
            viewport={"width": 1920, "height": 1080},
            screen={"width": 1920, "height": 1080},
            locale="en-AU",
            timezone_id="Australia/Sydney",
        )
        # Override navigator properties untuk bypass CF detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-AU', 'en'] });
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) =>
                p.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(p);
            window.chrome = { runtime: {} };
        """)
    else:
        # Context minimal untuk site biasa
        context = await browser.new_context(
            user_agent=_UA,
            locale="en-AU",
            timezone_id="Australia/Sydney",
        )

    return context


# ── Core async fetcher ─────────────────────────────────────────────────────────

async def _fetch_async(
    url: str,
    bypass_cf: bool,
    wait_for_selector: Optional[str],
    extra_wait_seconds: int,
) -> Optional[str]:

    async with async_playwright() as p:
        browser = await _build_browser(p, bypass_cf)
        context = await _build_context(browser, bypass_cf)
        page    = await context.new_page()

        # Stealth hanya diaktifkan saat bypass_cf
        if bypass_cf and _STEALTH_AVAILABLE:
            await stealth_async(page)
            logger.info("[Playwright] Stealth aktif (CF bypass mode).")
        elif bypass_cf and not _STEALTH_AVAILABLE:
            logger.warning("[Playwright] Stealth tidak aktif — install playwright-stealth.")

        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
        })

        page_load_timeout = _PAGE_LOAD_TIMEOUT_MS if bypass_cf else _HEADLESS_LOAD_TIMEOUT_MS

        try:
            logger.info(f"[Playwright] {'[CF] ' if bypass_cf else ''}Membuka: {url}")
            await page.goto(url, timeout=page_load_timeout, wait_until="domcontentloaded")

            # Khusus bypass_cf: tunggu Turnstile selesai
            if bypass_cf:
                if _is_cloudflare_page(await page.content()):
                    logger.info("[Playwright] CF challenge terdeteksi, menunggu auto-resolve...")
                    resolved = await _wait_for_turnstile(page)
                    if not resolved:
                        logger.error("[Playwright] Gagal melewati Cloudflare Turnstile.")
                        with open("debug_cf_blocked.html", "w", encoding="utf-8") as f:
                            f.write(await page.content())
                        return None

            # Tunggu selector konten muncul
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=_SELECTOR_WAIT_MS)
                    logger.info(f"[Playwright] Selector '{wait_for_selector}' ditemukan.")
                except PWTimeout:
                    logger.warning(
                        f"[Playwright] Selector '{wait_for_selector}' tidak muncul "
                        f"dalam {_SELECTOR_WAIT_MS/1000:.0f}s — lanjut ambil HTML."
                    )

            # Extra wait agar JS selesai render
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


# ── Public API ─────────────────────────────────────────────────────────────────

# Konstanta publik — bisa diimport scraper lain yang butuh nilai timeout
PAGE_LOAD_TIMEOUT_MS = _HEADLESS_LOAD_TIMEOUT_MS   # 30s, untuk non-CF sites
SELECTOR_TIMEOUT_MS  = _SELECTOR_WAIT_MS            # 30s, tunggu selector


async def create_browser_context(bypass_cf: bool = False):
    """
    Buat dan return (playwright_instance, browser, context) yang sudah dikonfigurasi.

    Digunakan oleh scraper yang butuh interaksi custom di dalam page
    (contoh: WA scraper yang perlu klik Show All + tunggu AJAX)
    sebelum mengambil HTML-nya.

    PENTING: Caller wajib menutup resource setelah selesai:

        pw, browser, context = await create_browser_context()
        try:
            page = await context.new_page()
            # ... interaksi custom ...
            html = await page.content()
        finally:
            await browser.close()
            await pw.stop()

    Parameters
    ----------
    bypass_cf : False (default) → headless biasa.
                True → non-headless + stealth untuk Cloudflare.

    Returns
    -------
    Tuple (playwright_instance, browser, context)
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "playwright tidak tersedia. "
            "Jalankan: pip install playwright && playwright install chromium"
        )

    from playwright.async_api import async_playwright as _async_playwright

    pw      = await _async_playwright().start()
    browser = await _build_browser(pw, bypass_cf)
    context = await _build_context(browser, bypass_cf)
    return pw, browser, context


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
    bypass_cf         : False (default) → headless biasa untuk 7 state normal.
                        True → non-headless + stealth khusus ACT (Cloudflare).

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