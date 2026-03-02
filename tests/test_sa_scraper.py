"""
Unit Tests — SA Scraper
=======================
Menguji fungsi _parse_sa_html dan _has_subclass
dari src/scrapers/sa_scraper.py.
SA scraper menggunakan card-based parsing: cari teks "ANZSCO XXXXXX",
lalu naik ke heading terdekat untuk dapat nama occupation.

Jalankan:
    pytest tests/test_sa_scraper.py -v
"""

import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.sa_scraper import _parse_sa_html, _has_subclass


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: HTML Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def make_sa_card_html(cards: list[dict]) -> str:
    """
    Buat HTML SA dengan beberapa occupation card.
    cards = [{"name": "Software Engineer", "code": "261311", "visa": ["190", "491"]}, ...]
    """
    body = ""
    for c in cards:
        visa_badges = " ".join(f"<span>Subclass {v}</span>" for v in c.get("visa", []))
        body += f"""
        <div class="occupation-card">
          <h3>{c['name']}</h3>
          <p>ANZSCO {c['code']}</p>
          {visa_badges}
        </div>
        """
    return f"<html><body>{body}</body></html>"


def make_sa_fallback_html(codes: list[str]) -> str:
    """HTML tanpa ANZSCO prefix — hanya angka 6 digit."""
    items = "".join(f"<p>{code} Some Occupation</p>" for code in codes)
    return f"<html><body>{items}</body></html>"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _has_subclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestHasSubclass:

    @pytest.mark.parametrize("text,subclass,expected", [
        ("Subclass 190 eligible", "190", True),
        ("visa 491 nomination",   "491", True),
        ("only 190 here",         "190", True),
        ("no visa info",          "190", False),
        ("491 stream available",  "491", True),
        ("",                      "190", False),
    ])
    def test_detection(self, text, subclass, expected):
        assert _has_subclass(text, subclass) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _parse_sa_html — card path
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseSaHtml:

    def test_parses_anzsco_code_from_card(self):
        html = make_sa_card_html([
            {"name": "Software Engineer", "code": "261311", "visa": ["190"]},
        ])
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert any(r["raw_code"] == "261311" for r in records)

    def test_parses_multiple_cards(self):
        html = make_sa_card_html([
            {"name": "Software Engineer", "code": "261311", "visa": ["190"]},
            {"name": "Civil Engineer",    "code": "233211", "visa": ["190", "491"]},
        ])
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert len(records) == 2

    def test_correct_state_in_record(self):
        html = make_sa_card_html([{"name": "Software Engineer", "code": "261311", "visa": ["190"]}])
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert all(r["state"] == "SA" for r in records)

    def test_dama_list_type(self):
        html = make_sa_card_html([{"name": "Chef", "code": "351311", "visa": ["491"]}])
        records = _parse_sa_html(html, state="SA", list_type="dama")
        assert records[0]["list_type"] == "dama"

    def test_visa_190_detected(self):
        html = make_sa_card_html([
            {"name": "Software Engineer", "code": "261311", "visa": ["190"]},
        ])
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert records[0]["visa_190"] is True

    def test_visa_491_detected(self):
        html = make_sa_card_html([
            {"name": "Civil Engineer", "code": "233211", "visa": ["491"]},
        ])
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert records[0]["visa_491"] is True

    def test_both_visas_detected(self):
        html = make_sa_card_html([
            {"name": "Veterinarian", "code": "234711", "visa": ["190", "491"]},
        ])
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is True

    def test_fallback_when_no_anzsco_prefix(self):
        """Jika tidak ada 'ANZSCO XXXXXX', fallback ke scan 6-digit angka."""
        html = make_sa_fallback_html(["261311", "233211"])
        records = _parse_sa_html(html, state="SA", list_type="main")
        codes = {r["raw_code"] for r in records}
        assert "261311" in codes
        assert "233211" in codes

    def test_empty_html_returns_empty(self):
        html = "<html><body><p>Nothing here</p></body></html>"
        records = _parse_sa_html(html, state="SA", list_type="main")
        assert records == []


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: scrape() entry — mock
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaScrapeEntryPoint:
    @patch("src.scrapers.sa_scraper.get_page_source")
    def test_returns_records(self, mock_gps):
        mock_gps.return_value = make_sa_card_html([
            {"name": "Software Engineer", "code": "261311", "visa": ["190"]},
        ])
        from src.scrapers.sa_scraper import scrape
        records = scrape("https://fake.sa.gov.au", list_type="main")
        assert len(records) >= 1

    @patch("src.scrapers.sa_scraper.get_page_source")
    def test_dama_entry_point(self, mock_gps):
        mock_gps.return_value = make_sa_card_html([
            {"name": "Chef", "code": "351311", "visa": ["491"]},
        ])
        from src.scrapers.sa_scraper import scrape
        records = scrape("https://fake.sa.gov.au", list_type="dama")
        assert records[0]["list_type"] == "dama"

    @patch("src.scrapers.sa_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.sa_scraper import scrape
        assert scrape("https://fake.sa.gov.au") == []
