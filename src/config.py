"""
Configuration file for the Immigration Data Scraper
"""
import os
from datetime import datetime
# TODO  target url is not valid {VIC}
# TODO ACT need adjustment(bypass cloudflare Turnstile)
# Target URLs — structured as list of dicts for easy iteration
TARGET_URLS = [
    {
        "state": "NSW",
        "list_type": "main",
        "url": "https://www.nsw.gov.au/visas-and-migration/skilled-visas/nsw-skills-lists"
    },
    {
        "state": "ACT",
        "list_type": "main",
        "url": "https://www.act.gov.au/migration/skilled-migrants/act-nominated-migration-program-occupation-list"
    },
    {
        "state": "VIC",
        "list_type": "main",
        "url": "https://liveinmelbourne.vic.gov.au/contact-us/registration-of-interest-roi-for-skilled-visa-nomination/what-of-the-following-topics-is-your-enquiry-related-to/nominated-occupation"
    },
    {
        "state": "QLD",
        "list_type": "onshore",
        "url": "https://migration.qld.gov.au/occupation-lists/queensland-onshore-skilled-occupation-list"
    },
    {
        "state": "QLD",
        "list_type": "offshore",
        "url": "https://migration.qld.gov.au/occupation-lists/offshore-queensland-skilled-occupation-lists-(qsol)"
    },
    {
        "state": "NT",
        "list_type": "main",
        "url": "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination/nt-offshore-migration-occupation-list"
    },
    {
        "state": "WA",
        "list_type": "main",
        "url": "https://migration.wa.gov.au/our-services-support/state-nominated-migration-program"
    },
    {
        "state": "SA",
        "list_type": "main",
        "url": "https://migration.sa.gov.au/before-applying/work-in-sa/occupation-lists/occupations-list"
    },
    {
        "state": "SA",
        "list_type": "dama",
        "url": "https://migration.sa.gov.au/before-applying/work-in-sa/occupation-lists/occupations-list-dama"
    },
    {
        "state": "TAS",
        "list_type": "main",
        "url": "https://www.migration.tas.gov.au/skilled_migration/subclass-190-tasmanian-skilled-employment-tse-priority-roles"
    },
]

# Master data for ANZSCO normalization
MASTER_DATA_PATH = "src/master_data/MASTER - anzsco 2022 structure_datacleaning.xlsx - ANZSCO 2022.csv"

# Scraping Configuration
HEADLESS_MODE = True  # Set to False to see browser during scraping
PAGE_LOAD_TIMEOUT = 30  # seconds
IMPLICIT_WAIT = 10  # seconds
SCROLL_PAUSE_TIME = 2  # seconds between scrolls

# Data Export Configuration
OUTPUT_DIR = "output"
EXPORT_FORMATS = ["csv", "json", "excel"]  # Available: csv, json, excel
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# File naming
def get_output_filename(extension, prefix="occupation_list"):
    """Generate output filename with timestamp"""
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    return f"{prefix}_{timestamp}.{extension}"

# Logging Configuration
LOG_DIR = "logs"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Create directories if they don't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Final output schema fields
DATA_FIELDS = [
    "state_code",
    "State Stream",
    "Requirements Overseas",
    "Requirements  Canberra Residents ",
    "Service fee",
]

# User Agent (to avoid being blocked)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
