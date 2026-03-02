"""
Unit Tests — VIC Scraper
========================
Menguji fungsi _parse_vic_html dari src/scrapers/vic_scraper.py.
VIC scraper mendukung: HTML table dan fallback scan ANZSCO code di teks.

Jalankan:
    pytest tests/test_vic_scraper.py -v
"""

import sys
import os
import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.vic_scraper import _parse_vic_html, _find_col, _safe_get, _is_eligible


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def make_vic_table_html(rows: list[tuple], headers=("ANZSCO Code", "Occupation", "190", "491")) -> str:
    header_html = "".join(f"<th>{h}</th>" for h in headers)
    rows_html = ""
    for r in rows:
        rows_html += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return f"""
    <html><body>
      <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </body></html>
    """


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestVicHelpers:

    def test_find_col_found(self):
        headers = ["anzsco code", "occupation title", "190 eligible", "491"]
        assert _find_col(headers, ["anzsco", "code"]) == 0
        assert _find_col(headers, ["190"]) == 2
        assert _find_col(headers, ["491"]) == 3

    def test_find_col_not_found(self):
        headers = ["name", "salary"]
        assert _find_col(headers, ["anzsco"]) is None

    def test_safe_get_valid(self):
        assert _safe_get(["261311", "Software Engineer"], 0) == "261311"
        assert _safe_get(["261311", "Software Engineer"], 1) == "Software Engineer"

    def test_safe_get_out_of_bounds(self):
        assert _safe_get(["only_one"], 5) is None

    def test_safe_get_none_idx(self):
        assert _safe_get(["a", "b"], None) is None

    def test_safe_get_empty_string(self):
        assert _safe_get([""], 0) is None

    @pytest.mark.parametrize("val,expected", [
        ("Yes", True), ("yes", True), ("y", True), ("✓", True),
        ("No", False), ("no", False), ("n", False), ("–", False),
        ("Software Engineer", True),  # non-empty, non-negative = eligible
        ("", False),
    ])
    def test_is_eligible(self, val, expected):
        assert _is_eligible(val) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _parse_vic_html — table path
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseVicHtml:

    def test_parses_table_rows(self):
        html = make_vic_table_html([
            ("261311", "Software Engineer", "Yes", "No"),
            ("233211", "Civil Engineer",    "Yes", "Yes"),
        ])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        # Hanya data rows yang dihitung, bukan header
        data = [r for r in records if r["raw_code"] and r["raw_code"].isdigit()]
        assert len(data) == 2

    def test_correct_state_and_list_type(self):
        html = make_vic_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        assert records[0]["state"] == "VIC"
        assert records[0]["list_type"] == "main"

    def test_visa_flags_from_table(self):
        html = make_vic_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        # Ambil record yang punya kode valid
        r = next(x for x in records if x["raw_code"] == "261311")
        assert r["visa_190"] is True
        assert r["visa_491"] is False

    def test_both_visa_eligible(self):
        html = make_vic_table_html([("233211", "Civil Engineer", "Yes", "Yes")])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is True

    def test_code_extracted_from_cell(self):
        html = make_vic_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        assert any(r["raw_code"] == "261311" for r in records)

    def test_fallback_scan_when_no_table(self):
        """Jika tidak ada table, scan ANZSCO code dari text halaman."""
        html = "<html><body><p>Occupation 261311 is listed here.</p></body></html>"
        records = _parse_vic_html(html, state="VIC", list_type="main")
        assert any(r["raw_code"] == "261311" for r in records)

    def test_empty_table_returns_no_records(self):
        html = make_vic_table_html([])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        # Tabel kosong = hanya header, tidak ada data rows
        data = [r for r in records if r.get("raw_code", "") and len(r["raw_code"]) == 6 and r["raw_code"].isdigit()]
        assert len(data) == 0

    def test_no_table_no_codes_returns_empty(self):
        html = "<html><body><p>No occupations here.</p></body></html>"
        records = _parse_vic_html(html, state="VIC", list_type="main")
        assert records == []

    def test_row_without_code_or_name_skipped(self):
        """Baris yang tidak punya code maupun name harus dilewati."""
        html = make_vic_table_html([
            ("", "", "Yes", "No"),              # kosong → skip
            ("261311", "Software Engineer", "Yes", "No"),  # valid
        ])
        records = _parse_vic_html(html, state="VIC", list_type="main")
        # Hanya record dengan kode ANZSCO valid
        data = [r for r in records if r.get("raw_code") == "261311"]
        assert len(data) == 1

    def test_table_without_190_491_columns_defaults_to_190_true(self):
        """Jika kolom 190/491 tidak ada → default visa_190=True."""
        html = make_vic_table_html(
            [("261311", "Software Engineer")],
            headers=("ANZSCO Code", "Occupation")
        )
        records = _parse_vic_html(html, state="VIC", list_type="main")
        assert records[0]["visa_190"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: scrape() entry — mock get_page_source
# ═══════════════════════════════════════════════════════════════════════════════

class TestVicScrapeEntryPoint:
    @patch("src.scrapers.vic_scraper.get_page_source")
    def test_returns_records(self, mock_gps):
        mock_gps.return_value = make_vic_table_html([
            ("261311", "Software Engineer", "Yes", "No"),
        ])
        from src.scrapers.vic_scraper import scrape
        records = scrape("https://fake.vic.gov.au")
        assert len(records) >= 1

    @patch("src.scrapers.vic_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.vic_scraper import scrape
        assert scrape("https://fake.vic.gov.au") == []
