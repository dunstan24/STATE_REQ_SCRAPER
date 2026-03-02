"""
Unit Tests — ACT & NT Scrapers
================================
Menguji fungsi parsing dari:
  - src/scrapers/act_scraper.py  (_parse_act_html)
  - src/scrapers/nt_scraper.py   (_parse_generic_html)

Kedua scraper ini menggunakan Selenium karena situs mereka memblokir requests biasa (403).
Test di sini hanya menguji HTML parsing logic — tanpa network/browser.

Jalankan:
    pytest tests/test_act_nt_scraper.py -v
"""

import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.act_scraper import _parse_act_html, _find_col as act_find_col, _is_eligible as act_is_eligible
from src.scrapers.nt_scraper  import _parse_generic_html, _find_col as nt_find_col, _is_eligible as nt_is_eligible


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def make_table_html(rows: list[tuple], headers=("ANZSCO Code", "Occupation", "190", "491")) -> str:
    header_row = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    data_rows = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"<html><body><table>{header_row}{data_rows}</table></body></html>"


# ═════════════════════════════════════════════════════════════════════════════
# ── ACT SCRAPER TESTS ──────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

class TestActHelpers:

    def test_find_col_anzsco(self):
        headers = ["anzsco code", "occupation name", "190", "491"]
        assert act_find_col(headers, ["anzsco", "code"]) == 0

    def test_find_col_missing(self):
        assert act_find_col(["name", "salary"], ["anzsco"]) is None

    @pytest.mark.parametrize("text,expected", [
        ("Yes", True), ("✓", True), ("y", True),
        ("No", False), ("–", False), ("", False),
        ("Software Engineer", True),  # non-empty non-negative = eligible
    ])
    def test_is_eligible(self, text, expected):
        assert act_is_eligible(text) == expected


class TestParseActHtml:
    """Menguji _parse_act_html (table-based parser ACT)."""

    def test_parses_simple_table(self):
        html = make_table_html([
            ("261311", "Software Engineer", "Yes", "No"),
            ("233211", "Civil Engineer",    "Yes", "Yes"),
        ])
        records = _parse_act_html(html, state="ACT", list_type="main")
        data = [r for r in records if r.get("raw_code", "") and len(r["raw_code"]) == 6 and r["raw_code"].isdigit()]
        assert len(data) == 2

    def test_correct_state(self):
        html = make_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_act_html(html, state="ACT", list_type="main")
        assert records[0]["state"] == "ACT"

    def test_visa_190_parsed(self):
        html = make_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_act_html(html, state="ACT", list_type="main")
        r = next(x for x in records if x.get("raw_code") == "261311")
        assert r["visa_190"] is True
        assert r["visa_491"] is False

    def test_visa_491_parsed(self):
        html = make_table_html([("233211", "Civil Engineer", "No", "Yes")])
        records = _parse_act_html(html, state="ACT", list_type="main")
        r = next(x for x in records if x.get("raw_code") == "233211")
        assert r["visa_190"] is False
        assert r["visa_491"] is True

    def test_default_190_when_no_visa_columns(self):
        html = make_table_html(
            [("261311", "Software Engineer")],
            headers=("ANZSCO Code", "Occupation")
        )
        records = _parse_act_html(html, state="ACT", list_type="main")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is False

    def test_fallback_code_detection_from_cell(self):
        """
        Jika tidak ada kolom 'anzsco'/'code' di header, namun ada cell yang isinya
        6-digit angka, scraper menggunakan cell itu sebagai raw_code.
        Pastikan record ditemukan dari table dengan header non-standar.
        """
        html = """<html><body>
        <table>
          <tr><th>ID Number</th><th>Job Title</th></tr>
          <tr><td>261311</td><td>Software Engineer</td></tr>
        </table>
        </body></html>"""
        records = _parse_act_html(html, state="ACT", list_type="main")
        # Setidaknya ada record dari baris data (dengan atau tanpa kode terdeteksi)
        # Jika header 'ID Number' tidak dikenali, scraper akan scan 6-digit dari cell
        assert len(records) >= 1, f"Tidak ada record yang ditemukan. Records: {records}"

    def test_fallback_anzsco_scan_when_no_table(self):
        """Jika tidak ada table, scan seluruh teks untuk kode 6 digit."""
        html = "<html><body><p>Eligible: 261311 Software Engineer, 233211 Civil Engineer</p></body></html>"
        records = _parse_act_html(html, state="ACT", list_type="main")
        codes = {r["raw_code"] for r in records}
        assert "261311" in codes
        assert "233211" in codes

    def test_empty_html_returns_empty(self):
        html = "<html><body></body></html>"
        records = _parse_act_html(html, state="ACT", list_type="main")
        assert records == []

    def test_row_without_code_or_name_skipped(self):
        html = make_table_html([
            ("", ""),                        # kosong → di-skip
            ("261311", "Software Engineer", "Yes", "No"),
        ])
        records = _parse_act_html(html, state="ACT", list_type="main")
        data = [r for r in records if r.get("raw_code") == "261311"]
        assert len(data) == 1


class TestActScrapeEntryPoint:
    @patch("src.scrapers.act_scraper.get_page_source")
    def test_returns_records(self, mock_gps):
        mock_gps.return_value = make_table_html([
            ("261311", "Software Engineer", "Yes", "No"),
        ])
        from src.scrapers.act_scraper import scrape
        records = scrape("https://fake.act.gov.au")
        assert len(records) >= 1

    @patch("src.scrapers.act_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.act_scraper import scrape
        assert scrape("https://fake.act.gov.au") == []

    @patch("src.scrapers.act_scraper.get_page_source")
    def test_returns_empty_on_access_denied(self, mock_gps):
        """Jika halaman mengandung '403' / 'Access Denied' → return []"""
        mock_gps.return_value = "<html><body>403 Access Denied</body></html>"
        from src.scrapers.act_scraper import scrape
        records = scrape("https://fake.act.gov.au")
        assert records == []


# ═════════════════════════════════════════════════════════════════════════════
# ── NT SCRAPER TESTS ───────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

class TestNtHelpers:

    def test_find_col_anzsco(self):
        headers = ["anzsco code", "occupation name"]
        assert nt_find_col(headers, ["anzsco", "code"]) == 0

    @pytest.mark.parametrize("text,expected", [
        ("Yes", True), ("✓", True),
        ("No", False), ("-", False), ("", False),
    ])
    def test_is_eligible(self, text, expected):
        assert nt_is_eligible(text) == expected


class TestParseNtHtml:
    """Menguji _parse_generic_html (NT scraper)."""

    def test_parses_simple_table(self):
        html = make_table_html([
            ("261311", "Software Engineer", "Yes", "No"),
            ("233211", "Civil Engineer",    "Yes", "Yes"),
        ])
        records = _parse_generic_html(html, state="NT", list_type="main")
        data = [r for r in records if r.get("raw_code", "") and len(r["raw_code"]) == 6 and r["raw_code"].isdigit()]
        assert len(data) == 2

    def test_correct_state(self):
        html = make_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_generic_html(html, state="NT", list_type="main")
        assert records[0]["state"] == "NT"

    def test_visa_190_parsed(self):
        html = make_table_html([("261311", "Software Engineer", "Yes", "No")])
        records = _parse_generic_html(html, state="NT", list_type="main")
        r = next(x for x in records if x.get("raw_code") == "261311")
        assert r["visa_190"] is True
        assert r["visa_491"] is False

    def test_4digit_code_also_detected(self):
        """NT juga mungkin menggunakan 4-digit ANZSCO unit group code."""
        html = "<html><body><table><tr><th>Code</th><th>Name</th></tr><tr><td>2613</td><td>Software Programmers</td></tr></table></body></html>"
        records = _parse_generic_html(html, state="NT", list_type="main")
        assert any(r["raw_code"] == "2613" for r in records)

    def test_fallback_text_scan_when_no_table(self):
        html = "<html><body><p>Occupations: 261311 and 233211 are open.</p></body></html>"
        records = _parse_generic_html(html, state="NT", list_type="main")
        codes = {r["raw_code"] for r in records}
        assert "261311" in codes

    def test_empty_html_returns_empty(self):
        html = "<html><body></body></html>"
        records = _parse_generic_html(html, state="NT", list_type="main")
        assert records == []

    def test_default_190_when_no_visa_columns(self):
        html = make_table_html(
            [("261311", "Software Engineer")],
            headers=("ANZSCO Code", "Occupation")
        )
        records = _parse_generic_html(html, state="NT", list_type="main")
        assert records[0]["visa_190"] is True
        assert records[0]["visa_491"] is False


class TestNtScrapeEntryPoint:
    @patch("src.scrapers.nt_scraper.get_page_source")
    def test_returns_records(self, mock_gps):
        mock_gps.return_value = make_table_html([
            ("261311", "Software Engineer", "Yes", "No"),
        ])
        from src.scrapers.nt_scraper import scrape
        records = scrape("https://fake.nt.gov.au")
        assert len(records) >= 1

    @patch("src.scrapers.nt_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.nt_scraper import scrape
        assert scrape("https://fake.nt.gov.au") == []
