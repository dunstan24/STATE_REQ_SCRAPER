"""
Unit Tests — TAS Scraper
========================
Menguji fungsi _parse_tas_html dari src/scrapers/tas_scraper.py.
TAS scraper mendukung: HTML table, fallback <li> list, fallback full text scan.
TAS spesifik untuk Subclass 190 (TSE Priority Roles).

Jalankan:
    pytest tests/test_tas_scraper.py -v
"""

import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.tas_scraper import _parse_tas_html, _find_col, _safe_get, _is_eligible


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def make_tas_table_html(rows: list[tuple], headers=("ANZSCO Code", "Occupation")) -> str:
    header_row = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    data_rows = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"<html><body><table>{header_row}{data_rows}</table></body></html>"


def make_tas_list_html(items: list[str]) -> str:
    li_items = "".join(f"<li>{item}</li>" for item in items)
    return f"<html><body><ul>{li_items}</ul></body></html>"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestTasHelpers:

    def test_find_col_code(self):
        headers = ["anzsco code", "occupation title"]
        assert _find_col(headers, ["anzsco", "code"]) == 0

    def test_find_col_role(self):
        headers = ["code", "role name"]
        assert _find_col(headers, ["occupation", "title", "role", "name"]) == 1

    def test_safe_get_valid(self):
        assert _safe_get(["261311", "Software Engineer"], 1) == "Software Engineer"

    def test_safe_get_empty(self):
        assert _safe_get([""], 0) is None

    @pytest.mark.parametrize("val,expected", [
        ("Yes", True), ("✓", True), ("No", False), ("", False),
    ])
    def test_is_eligible(self, val, expected):
        assert _is_eligible(val) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _parse_tas_html — table path
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseTasHtml:

    def test_parses_table(self):
        html = make_tas_table_html([
            ("261311", "Software Engineer"),
            ("233211", "Civil Engineer"),
        ])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        # Filter hanya record dengan 6-digit ANZSCO code
        data = [r for r in records if r.get("raw_code", "") and len(r["raw_code"]) == 6 and r["raw_code"].isdigit()]
        assert len(data) == 2

    def test_correct_state_in_record(self):
        html = make_tas_table_html([("261311", "Software Engineer")])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        assert records[0]["state"] == "TAS"

    def test_tas_default_190_true(self):
        """TAS adalah halaman Subclass 190 — default visa_190=True."""
        html = make_tas_table_html([("261311", "Software Engineer")])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        assert records[0]["visa_190"] is True

    def test_tas_default_491_false(self):
        """TAS tidak mention 491 secara eksplisit — default visa_491=False."""
        html = make_tas_table_html([("261311", "Software Engineer")])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        assert records[0]["visa_491"] is False

    def test_code_extracted_from_cell_fallback(self):
        """Jika header tidak ada 'anzsco', fallback deteksi dari isi cell."""
        html = make_tas_table_html(
            [("261311", "Software Engineer")],
            headers=("ID", "Role")
        )
        records = _parse_tas_html(html, state="TAS", list_type="main")
        assert any(r["raw_code"] == "261311" for r in records)

    def test_row_without_code_or_name_skipped(self):
        html = make_tas_table_html([
            ("", ""),                           # kosong
            ("261311", "Software Engineer"),    # valid
        ])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        data = [r for r in records if r.get("raw_code") == "261311"]
        assert len(data) == 1

    # ── Fallback: <li> list ───────────────────────────────────────────────────

    def test_fallback_li_when_no_table(self):
        html = make_tas_list_html([
            "261311 Software Engineer",
            "233211 Civil Engineer",
        ])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        assert len(records) == 2

    def test_fallback_li_extracts_code(self):
        html = make_tas_list_html(["261311 Software Engineer"])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        assert records[0]["raw_code"] == "261311"

    def test_fallback_li_extracts_name(self):
        html = make_tas_list_html(["261311 Software Engineer"])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        name = records[0]["raw_name"]
        assert name is not None
        assert "Software Engineer" in name

    def test_short_li_items_skipped(self):
        """<li> dengan teks < 3 karakter dilewati."""
        html = make_tas_list_html(["AB", "261311 Software Engineer"])
        records = _parse_tas_html(html, state="TAS", list_type="main")
        short = [r for r in records if r["raw_name"] == "AB"]
        assert short == []

    # ── Fallback: full text scan ──────────────────────────────────────────────

    def test_fallback_text_scan_when_no_table_or_list(self):
        html = "<html><body><p>Key roles: 261311 and 233211 are required.</p></body></html>"
        records = _parse_tas_html(html, state="TAS", list_type="main")
        codes = {r["raw_code"] for r in records}
        assert "261311" in codes


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: scrape() entry — mock
# ═══════════════════════════════════════════════════════════════════════════════

class TestTasScrapeEntryPoint:
    @patch("src.scrapers.tas_scraper.get_page_source")
    def test_returns_records(self, mock_gps):
        mock_gps.return_value = make_tas_table_html([
            ("261311", "Software Engineer"),
        ])
        from src.scrapers.tas_scraper import scrape
        records = scrape("https://fake.migration.tas.gov.au")
        assert len(records) >= 1

    @patch("src.scrapers.tas_scraper.get_page_source")
    def test_returns_empty_when_no_html(self, mock_gps):
        mock_gps.return_value = None
        from src.scrapers.tas_scraper import scrape
        assert scrape("https://fake.migration.tas.gov.au") == []
