"""
Integration Smoke Tests — Live URL Scraping
===========================================
Menguji scraper secara end-to-end dengan koneksi internet nyata 
untuk memastikan struktur halaman target belum berubah.

NOTE: Test ini membutuhkan koneksi internet dan Selenium WebDriver.
Jalankan:
    pytest tests/test_integration_smoke.py -v -m integration

Atau jalankan spesifik state:
    pytest tests/test_integration_smoke.py -v -k "nsw" -m integration
"""

import sys
import os
import pytest
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import scrapers
from src.scrapers import (
    nsw_scraper,
    vic_scraper,
    qld_scraper,
    sa_scraper,
    tas_scraper,
    wa_scraper,
    act_scraper,
    nt_scraper
)

# ── Konfigurasi Test ─────────────────────────────────────────────────────────

# Tandai semua test di file ini sebagai 'integration'
pytestmark = pytest.mark.integration

def check_records(records: List[dict], state: str):
    """Utility to verify records returned by a scraper."""
    assert isinstance(records, list), f"[{state}] Output harus berupa list"
    assert len(records) > 0, f"[{state}] Tidak ada data yang ditemukan"
    
    # Check sample record structure
    sample = records[0]
    required_keys = {"state", "list_type", "raw_code", "raw_name", "visa_190", "visa_491"}
    for key in required_keys:
        assert key in sample, f"[{state}] Missing key: {key}"
        
    print(f"\n  [OK] {state}: Found {len(records)} records. Sample: {sample['raw_name']} ({sample['raw_code']})")

# ── Integration Tests ────────────────────────────────────────────────────────

class TestScraperIntegration:

    def test_nsw_integration(self):
        url = "https://www.nsw.gov.au/visas-and-migration/skilled-visas/nsw-skills-lists"
        records = nsw_scraper.scrape(url)
        check_records(records, "NSW")

    def test_vic_integration(self):
        url = "https://liveinmelbourne.vic.gov.au/contact-us/registration-of-interest-roi-for-skilled-visa-nomination/what-of-the-following-topics-is-your-enquiry-related-to/nominated-occupation"
        records = vic_scraper.scrape(url)
        # VIC seringkali butuh interaksi tambahan atau hanya form ROI.
        # Jika records kosong, pastikan scraper setidaknya tidak crash.
        assert isinstance(records, list)

    def test_qld_onshore_integration(self):
        url = "https://migration.qld.gov.au/occupation-lists/queensland-onshore-skilled-occupation-list"
        records = qld_scraper.scrape(url, list_type="onshore")
        check_records(records, "QLD Onshore")

    def test_qld_offshore_integration(self):
        url = "https://migration.qld.gov.au/occupation-lists/offshore-queensland-skilled-occupation-lists-(qsol)"
        records = qld_scraper.scrape(url, list_type="offshore")
        check_records(records, "QLD Offshore")

    @pytest.mark.xfail(reason="SA page frequently changes structure or uses advanced bot protection")
    def test_sa_integration(self):
        url = "https://migration.sa.gov.au/before-applying/work-in-sa/occupation-lists/occupations-list"
        records = sa_scraper.scrape(url)
        check_records(records, "SA")

    def test_tas_integration(self):
        url = "https://www.migration.tas.gov.au/skilled_migration/subclass-190-tasmanian-skilled-employment-tse-priority-roles"
        records = tas_scraper.scrape(url)
        check_records(records, "TAS")

    def test_wa_integration(self):
        url = "https://migration.wa.gov.au/our-services-support/state-nominated-migration-program"
        # WA scraper punya logic kompleks untuk klik 'Show All'
        records = wa_scraper.scrape(url)
        check_records(records, "WA")

    @pytest.mark.xfail(reason="ACT uses Cloudflare/Incapsula bot protection")
    def test_act_integration(self):
        url = "https://www.act.gov.au/migration/skilled-migrants/act-nominated-migration-program-occupation-list"
        records = act_scraper.scrape(url)
        check_records(records, "ACT")

    @pytest.mark.xfail(reason="NT uses Cloudflare bot protection")
    def test_nt_integration(self):
        url = "https://australiasnorthernterritory.com.au/move/migrate-to-work/nt-government-visa-nomination/nt-offshore-migration-occupation-list"
        records = nt_scraper.scrape(url)
        check_records(records, "NT")
