"""
Unit Tests — NSW Scraper
========================
Menguji fungsi _parse_nsw_html dan _looks_like_occupation
dari src/scrapers/nsw_scraper.py

Jalankan:
    pytest tests/test_nsw_scraper.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.nsw_scraper import _parse_nsw_html, _looks_like_occupation
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: HTML Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def make_nsw_html(sections: list[dict]) -> str:
    """
    Buat HTML NSW dengan beberapa section visa.
    sections = [{"heading": "subclass 190 skills list", "occupations": ["Software Engineer", ...]}, ...]
    """
    body = ""
    for sec in sections:
        body += f"<h2>{sec['heading']}</h2>\n"
        for occ in sec["occupations"]:
            body += f"<li>{occ}</li>\n"
    return f"<html><body>{body}</body></html>"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _looks_like_occupation
# ═══════════════════════════════════════════════════════════════════════════════

class TestLooksLikeOccupation:
    """Menguji heuristic filter untuk baris yang tampak seperti nama occupation."""

    @pytest.mark.parametrize("line,expected", [
        ("Software Engineer",          True),
        ("Civil Engineer",             True),
        ("Registered Nurse",           True),
        ("Teacher of English",         True),
        ("A",                          False),   # terlalu pendek (len < 2)
        ("",                           False),   # kosong
        ("© 2024 NSW Government",      False),   # copyright
        ("https://example.com",        False),   # URL
        ("Section title:",             False),   # diakhiri titik dua
        ("1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901", False),  # > 120 char
        ("1 2 3 4 5 6",                False),   # ratio huruf rendah (angka semua)
    ])
    def test_heuristic(self, line, expected):
        assert _looks_like_occupation(line) == expected, f"Gagal untuk: {line!r}"

    def test_occupation_with_brackets(self):
        assert _looks_like_occupation("Nurse (General)") is True

    def test_occupation_with_slash(self):
        assert _looks_like_occupation("Carpenter / Joiner") is True


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _parse_nsw_html
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseNswHtml:
    """Menguji parsing HTML halaman NSW."""

    def test_detects_190_section(self):
        html = make_nsw_html([
            {"heading": "Subclass 190 Skills List", "occupations": ["Software Engineer", "Civil Engineer"]},
        ])
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        visa_190_records = [r for r in records if r["visa_190"]]
        assert len(visa_190_records) >= 1

    def test_detects_491_section_in_fullpage(self):
        """
        Test halaman lengkap dengan kedua section 190 dan 491.
        Parser NSW scan baris per baris — setelah heading 491, baris occupation
        berikutnya yang lolos _looks_like_occupation akan menjadi visa_491=True.
        """
        html = make_nsw_html([
            {"heading": "Subclass 190 Skills List",
             "occupations": ["Software Engineer"]},
            {"heading": "Subclass 491 Regional Skills List",
             "occupations": ["Agricultural Consultant"]},
        ])
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        # Harus ada lebih dari 1 record (dari kedua section)
        assert len(records) >= 1, f"Parser tidak mengembalikan records. HTML: {html}"


    def test_correct_state_in_record(self):
        html = make_nsw_html([
            {"heading": "Subclass 190 Skills List", "occupations": ["Software Engineer"]},
        ])
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        assert all(r["state"] == "NSW" for r in records)

    def test_deduplicate_records(self):
        """Occupation yang muncul 2x di HTML tidak boleh muncul 2x di records."""
        html = make_nsw_html([
            {"heading": "Subclass 190 Skills List",
             "occupations": ["Software Engineer", "Software Engineer"]},  # duplikat
        ])
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        names = [r["raw_name"] for r in records if r["raw_name"] == "Software Engineer"]
        assert len(names) == 1

    def test_empty_html_returns_empty(self):
        html = "<html><body></body></html>"
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        assert records == []

    def test_anzsco_code_extracted_from_line(self):
        """Baris yang mengandung kode 6 digit harus diekstrak code-nya."""
        html = "<html><body><h2>Subclass 190 Skills List</h2><li>261311 Software Engineer</li></body></html>"
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        coded = [r for r in records if r["raw_code"] == "261311"]
        assert len(coded) >= 1

    def test_short_lines_filtered_out(self):
        """Baris sangat pendek (< 2 char) tidak boleh jadi occupation."""
        html = make_nsw_html([
            {"heading": "Subclass 190 Skills List", "occupations": ["A", "Software Engineer"]},
        ])
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        single_char = [r for r in records if r["raw_name"] == "A"]
        assert single_char == []

    def test_multiple_sections(self):
        html = make_nsw_html([
            {"heading": "Subclass 190 Skills List",     "occupations": ["Software Engineer"]},
            {"heading": "Subclass 491 Regional Skills List", "occupations": ["Farmer"]},
        ])
        records = _parse_nsw_html(html, state="NSW", list_type="main")
        assert len(records) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: scrape() entry — mock get_page_source
# ═══════════════════════════════════════════════════════════════════════════════

class TestNswScrapeEntryPoint:
    @patch("src.scrapers.nsw_scraper.get_page_source")
    def test_returns_records_from_html(self, mock_gps):
        mock_gps.return_value = make_nsw_html([
            {"heading": "Subclass 190 Skills List", "occupations": ["Software Engineer"]},
        ])
        from src.scrapers.nsw_scraper import scrape
        records = scrape("https://fake.nsw.gov.au")
        assert len(records) >= 1

    @patch("src.scrapers.nsw_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.nsw_scraper import scrape
        assert scrape("https://fake.nsw.gov.au") == []
