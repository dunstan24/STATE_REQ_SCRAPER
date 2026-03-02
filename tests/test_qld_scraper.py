"""
Unit Tests — QLD Scraper
========================
Menguji fungsi _parse_qld_html dari src/scrapers/qld_scraper.py.
QLD scraper menggunakan HTML table dengan kolom ANZSCO Code, Occupation, 190, 491.

Jalankan:
    pytest tests/test_qld_scraper.py -v
"""

import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.qld_scraper import _parse_qld_html, _find_col, _safe_get, _is_eligible


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def make_qld_html(rows: list[tuple], headers=("ANZSCO Code", "Occupation", "190", "491")) -> str:
    header_row = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    data_rows = ""
    for r in rows:
        data_rows += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return f"""
    <html><body>
      <table>
        {header_row}
        {data_rows}
      </table>
    </body></html>
    """


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestQldHelpers:

    def test_find_col_anzsco(self):
        headers = ["anzsco code", "occupation", "190", "491"]
        assert _find_col(headers, ["anzsco", "code"]) == 0

    def test_find_col_190(self):
        assert _find_col(["anzsco", "name", "190 eligible"], ["190"]) == 2

    def test_find_col_missing(self):
        assert _find_col(["name", "salary"], ["anzsco"]) is None

    @pytest.mark.parametrize("val,expected", [
        ("Yes", True), ("✓", True), ("y", True),
        ("No", False), ("–", False), ("", False),
    ])
    def test_is_eligible(self, val, expected):
        assert _is_eligible(val) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _parse_qld_html
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseQldHtml:

    def test_parses_table_rows(self):
        html = make_qld_html([
            ("261311", "Software Engineer", "Yes", "No"),
            ("233211", "Civil Engineer",    "Yes", "Yes"),
        ])
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert len(records) == 2

    def test_correct_state_and_list_type(self):
        html = make_qld_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_qld_html(html, state="QLD", list_type="offshore")
        assert records[0]["state"] == "QLD"
        assert records[0]["list_type"] == "offshore"

    def test_visa_190_parsed_correctly(self):
        html = make_qld_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is False

    def test_visa_491_parsed_correctly(self):
        html = make_qld_html([("233211", "Civil Engineer", "No", "Yes")])
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert records[0]["visa_190"] is False
        assert records[0]["visa_491"] is True

    def test_both_eligible(self):
        html = make_qld_html([("234711", "Veterinarian", "Yes", "Yes")])
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is True

    def test_no_table_returns_empty(self):
        html = "<html><body><p>No table here.</p></body></html>"
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert records == []

    def test_empty_table_returns_empty(self):
        html = make_qld_html([])
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert records == []

    def test_default_both_true_when_no_visa_columns(self):
        """Jika tidak ada kolom 190/491, default keduanya True."""
        html = make_qld_html(
            [("261311", "Software Engineer")],
            headers=("ANZSCO Code", "Occupation")
        )
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is True

    def test_code_detected_from_cell_without_header(self):
        """Jika kolom code tidak teridentifikasi via header, deteksi dari cell."""
        html = make_qld_html(
            [("261311", "Software Engineer", "Yes", "No")],
            headers=("ID", "Role", "190", "491")   # tidak ada "anzsco" di header
        )
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        # Minimal harus ada 1 record (fallback cell scan)
        assert len(records) >= 1

    def test_header_rows_skipped(self):
        """Baris yang isinya 'anzsco', 'code', 'occupation' dianggap header → di-skip."""
        html = make_qld_html([
            ("ANZSCO", "Occupation", "190", "491"),   # pseudo header row
            ("261311", "Software Engineer", "Yes", "No"),
        ])
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        # Only 1 data row, not 2
        assert len(records) == 1

    def test_multiple_tables(self):
        """QLD mungkin punya lebih dari 1 table (onshore + offshore di halaman sama)."""
        table1 = "<table><tr><th>ANZSCO Code</th><th>Occupation</th></tr><tr><td>261311</td><td>Software Engineer</td></tr></table>"
        table2 = "<table><tr><th>ANZSCO Code</th><th>Occupation</th></tr><tr><td>233211</td><td>Civil Engineer</td></tr></table>"
        html = f"<html><body>{table1}{table2}</body></html>"
        records = _parse_qld_html(html, state="QLD", list_type="onshore")
        assert len(records) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: scrape() entry — mock
# ═══════════════════════════════════════════════════════════════════════════════

class TestQldScrapeEntryPoint:
    @patch("src.scrapers.qld_scraper.get_page_source")
    def test_returns_records(self, mock_gps):
        mock_gps.return_value = make_qld_html([
            ("261311", "Software Engineer", "Yes", "No"),
        ])
        from src.scrapers.qld_scraper import scrape
        records = scrape("https://fake.qld.gov.au", list_type="onshore")
        assert len(records) >= 1

    @patch("src.scrapers.qld_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.qld_scraper import scrape
        assert scrape("https://fake.qld.gov.au") == []
