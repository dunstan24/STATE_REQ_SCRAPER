"""
Scrapers package — one module per state.
Each scraper exposes a single function: scrape(url, state, list_type, **kwargs) -> list[dict]

Raw record format returned by all scrapers:
{
    "state":      str,   # e.g. "QLD"
    "list_type":  str,   # e.g. "onshore"
    "raw_code":   str,   # ANZSCO code as scraped (may be 4 or 6 digits, or None)
    "raw_name":   str,   # Occupation / unit group name as scraped (may be None)
    "visa_190":   bool,  # True if eligible for subclass 190
    "visa_491":   bool,  # True if eligible for subclass 491
}
"""

from .nsw_scraper import scrape as scrape_nsw
from .act_scraper import scrape as scrape_act
from .vic_scraper import scrape as scrape_vic
from .qld_scraper import scrape as scrape_qld
from .nt_scraper  import scrape as scrape_nt
from .wa_scraper  import scrape as scrape_wa
from .sa_scraper  import scrape as scrape_sa
from .tas_scraper import scrape as scrape_tas

# Map state codes to their scraper functions
SCRAPER_MAP = {
    "NSW": scrape_nsw,
    "ACT": scrape_act,
    "VIC": scrape_vic,
    "QLD": scrape_qld,
    "NT":  scrape_nt,
    "WA":  scrape_wa,
    "SA":  scrape_sa,
    "TAS": scrape_tas,
}


def get_scraper(state: str):
    """Return the scraper function for a given state code."""
    scraper = SCRAPER_MAP.get(state.upper())
    if not scraper:
        raise ValueError(f"No scraper registered for state: {state}")
    return scraper
