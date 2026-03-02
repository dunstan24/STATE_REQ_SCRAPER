"""
Unit tests for wa_scraper.py
============================
Menguji setiap fungsi secara terpisah tanpa Selenium / internet.
Selenium di-mock sehingga test ini bisa dijalankan di mana saja.

Jalankan dengan:
    pytest tests/test_wa_scraper.py -v
"""

import io
import csv
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
from bs4 import BeautifulSoup
import pytest

# Pastikan root project ada di sys.path agar import src berfungsi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.wa_scraper import (
    _csv_is_eligible,
    _find_in_row,
    _has_subclass_in_row,
    _extract_row_data,
    _parse_wa_html,
    _scrape_via_csv,
    scrape,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: HTML Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def make_row_html(code: str, name: str, cls_190: str = "", cls_491: str = "", extra: str = "") -> str:
    """Buat HTML satu occupation row untuk testing."""
    badge_190 = f'<span class="field-190">{cls_190}</span>' if cls_190 else ""
    badge_491 = f'<span class="field-491">{cls_491}</span>' if cls_491 else ""
    return f"""
    <div class="occupation views-row">
      <div class="views-field-field-anzsco-code">{code}</div>
      <div class="views-field-title">{name}</div>
      {badge_190}
      {badge_491}
      {extra}
    </div>
    """


def make_full_html(*rows: str) -> str:
    """Bungkus beberapa rows dalam struktur halaman WA."""
    inner = "\n".join(rows)
    return f"""
    <html><body>
      <div class="view-content">
        {inner}
      </div>
    </body></html>
    """


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _csv_is_eligible
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvIsEligible:
    """Menguji logic eligibility dari nilai kolom CSV."""

    @pytest.mark.parametrize("val,expected", [
        ("yes",     True),
        ("Yes",     True),
        ("YES",     True),
        ("y",       True),
        ("Y",       True),
        ("1",       True),
        ("true",    True),
        ("True",    True),
        ("✓",       True),
        ("✔",       True),
        ("eligible",True),
        ("no",      False),
        ("No",      False),
        ("n",       False),
        ("0",       False),
        ("false",   False),
        ("",        False),
        ("  ",      False),
        ("maybe",   False),
        ("ineligible", False),
    ])
    def test_values(self, val, expected):
        assert _csv_is_eligible(val) == expected, f"_csv_is_eligible({val!r}) harus {expected}"

    def test_none_returns_false(self):
        assert _csv_is_eligible(None) is False

    def test_whitespace_stripped(self):
        assert _csv_is_eligible("  yes  ") is True
        assert _csv_is_eligible("  no  ") is False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _find_in_row
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindInRow:
    """Menguji pencarian nilai berdasarkan keyword di key dict."""

    def test_finds_anzsco_key(self):
        row = {"ANZSCO Code": "261311", "Occupation": "Software Engineer"}
        assert _find_in_row(row, ["anzsco", "code"]) == "261311"

    def test_finds_occupation_key(self):
        row = {"ANZSCO Code": "261311", "Occupation Title": "Software Engineer"}
        assert _find_in_row(row, ["occupation", "title", "name"]) == "Software Engineer"

    def test_returns_none_when_not_found(self):
        row = {"Something": "abc", "Other": "xyz"}
        assert _find_in_row(row, ["anzsco", "code"]) is None

    def test_strips_whitespace(self):
        row = {"anzsco_code": "  261311  "}
        result = _find_in_row(row, ["anzsco"])
        assert result == "261311"

    def test_case_insensitive_key_match(self):
        row = {"ANZSCO_CODE": "261311"}
        assert _find_in_row(row, ["anzsco"]) == "261311"

    def test_empty_value_returns_none(self):
        row = {"anzsco": ""}
        assert _find_in_row(row, ["anzsco"]) is None

    def test_first_match_returned(self):
        row = {"190 eligible": "Yes", "491 eligible": "No"}
        result = _find_in_row(row, ["190"])
        assert result == "Yes"

    def test_partial_key_match(self):
        row = {"visa_190_status": "Yes"}
        assert _find_in_row(row, ["190"]) == "Yes"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _has_subclass_in_row
# ═══════════════════════════════════════════════════════════════════════════════

class TestHasSubclassInRow:
    """Menguji deteksi visa subclass dalam HTML row."""

    def _row(self, html: str):
        return BeautifulSoup(html, "lxml").find(class_="occupation")

    def test_190_detected_by_class_yes(self):
        html = '<div class="occupation"><span class="field-190">Yes</span></div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "190") is True

    def test_190_detected_by_class_checkmark(self):
        html = '<div class="occupation"><span class="field-190">✓</span></div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "190") is True

    def test_491_detected_by_class_eligible(self):
        html = '<div class="occupation"><td class="col-491">eligible</td></div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "491") is True

    def test_190_no_when_class_says_no(self):
        html = '<div class="occupation"><span class="field-190">No</span></div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "190") is False

    def test_detected_via_text_pattern(self):
        html = '<div class="occupation">This occupation is eligible for subclass 491 nomination</div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "491") is True

    def test_visa_word_pattern(self):
        html = '<div class="occupation">visa 190 eligible</div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "190") is True

    def test_not_detected_when_absent(self):
        html = '<div class="occupation"><p>Software Engineer 261311</p></div>'
        row = self._row(html)
        # Tidak ada referensi 491 → False
        assert _has_subclass_in_row(row, "491") is False

    def test_491_nomination_pattern(self):
        html = '<div class="occupation">491 nomination available</div>'
        row = self._row(html)
        assert _has_subclass_in_row(row, "491") is True


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _extract_row_data
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractRowData:
    """Menguji ekstraksi ANZSCO code, nama, dan visa dari satu row HTML."""

    def _row(self, html: str):
        return BeautifulSoup(html, "lxml").find(class_="occupation")

    def test_extracts_6digit_anzsco_code(self):
        html = make_row_html("261311", "Software Engineer")
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert code == "261311"

    def test_extracts_occupation_name(self):
        html = make_row_html("261311", "Software Engineer")
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert name == "Software Engineer"

    def test_fallback_to_row_text_for_code(self):
        # Code bukan di element dengan class 'anzsco', tapi ada di teks row
        html = '<div class="occupation views-row"><p>261311 - Software Engineer</p></div>'
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert code == "261311"

    def test_default_190_when_no_visa_info(self):
        """Jika tidak ada visa info, defaultnya 190=True."""
        html = make_row_html("261311", "Software Engineer")
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert v190 is True

    def test_explicit_190_eligible(self):
        html = make_row_html("261311", "Software Engineer", cls_190="Yes")
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert v190 is True

    def test_explicit_491_eligible(self):
        html = make_row_html("261311", "Software Engineer", cls_491="Yes")
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert v491 is True

    def test_no_code_returns_none(self):
        html = '<div class="occupation views-row"><div class="views-field-title">Occupation Without Code</div></div>'
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        assert code is None

    def test_pure_number_not_treated_as_name(self):
        """Element yang isinya pure angka tidak dijadikan occupation name."""
        html = '<div class="occupation views-row"><div class="views-field-title">261311</div><h2>Real Name</h2></div>'
        row = self._row(html)
        code, name, v190, v491 = _extract_row_data(row)
        # name tidak boleh "261311"
        assert name != "261311"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _parse_wa_html
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseWaHtml:
    """Menguji parsing HTML penuh dari halaman WA."""

    def test_parses_multiple_rows(self):
        html = make_full_html(
            make_row_html("261311", "Software Engineer"),
            make_row_html("261313", "Software Tester"),
            make_row_html("233211", "Civil Engineer"),
        )
        records = _parse_wa_html(html, state="WA", list_type="main")
        assert len(records) == 3

    def test_record_fields_present(self):
        html = make_full_html(make_row_html("261311", "Software Engineer"))
        records = _parse_wa_html(html, state="WA", list_type="main")
        assert len(records) == 1
        r = records[0]
        assert r["state"] == "WA"
        assert r["list_type"] == "main"
        assert r["raw_code"] == "261311"
        assert r["raw_name"] == "Software Engineer"
        assert "visa_190" in r
        assert "visa_491" in r

    def test_empty_html_returns_empty_list(self):
        html = "<html><body><div class='view-content'></div></body></html>"
        records = _parse_wa_html(html, state="WA", list_type="main")
        assert records == []

    def test_fallback_when_view_content_missing(self):
        """Jika div.view-content tidak ada, parse seluruh halaman."""
        html = """
        <html><body>
          <div class="occupation views-row">
            <div class="views-field-field-anzsco-code">261311</div>
            <div class="views-field-title">Software Engineer</div>
          </div>
        </body></html>
        """
        records = _parse_wa_html(html, state="WA", list_type="main")
        # Masih bisa menemukan record meski tidak ada view-content wrapper
        assert len(records) >= 1

    def test_row_without_code_or_name_skipped(self):
        """Row yang tidak punya code maupun name harus dilewati."""
        html = make_full_html(
            make_row_html("261311", "Software Engineer"),   # valid
            '<div class="occupation views-row"><p>nothing useful</p></div>',  # no code/name
        )
        records = _parse_wa_html(html, state="WA", list_type="main")
        # Minimal 1 record dari row pertama
        assert len(records) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: _scrape_via_csv (mock requests.get)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScrapeViaCsv:
    """Menguji CSV fallback scraper dengan HTTP di-mock."""

    def _make_csv_response(self, rows: list[dict]) -> str:
        """Buat string CSV dari list of dict."""
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    @patch("src.scrapers.wa_scraper.requests.get")
    def test_parses_valid_csv(self, mock_get):
        csv_data = self._make_csv_response([
            {"ANZSCO Code": "261311", "Occupation": "Software Engineer", "190": "Yes", "491": "No"},
            {"ANZSCO Code": "233211", "Occupation": "Civil Engineer",    "190": "Yes", "491": "Yes"},
        ])
        mock_resp = MagicMock()
        mock_resp.text = csv_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        records = _scrape_via_csv(state="WA", list_type="main")
        assert len(records) == 2

    @patch("src.scrapers.wa_scraper.requests.get")
    def test_record_fields_correct(self, mock_get):
        csv_data = self._make_csv_response([
            {"ANZSCO Code": "261311", "Occupation Title": "Software Engineer", "190": "Yes", "491": "No"},
        ])
        mock_resp = MagicMock()
        mock_resp.text = csv_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        records = _scrape_via_csv(state="WA", list_type="main")
        assert len(records) == 1
        r = records[0]
        assert r["raw_code"] == "261311"
        assert r["visa_190"] is True
        assert r["visa_491"] is False

    @patch("src.scrapers.wa_scraper.requests.get")
    def test_default_190_when_no_visa_columns(self, mock_get):
        """Jika CSV tidak punya kolom 190/491 → default visa_190=True."""
        csv_data = self._make_csv_response([
            {"ANZSCO Code": "261311", "Occupation": "Software Engineer"},
        ])
        mock_resp = MagicMock()
        mock_resp.text = csv_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        records = _scrape_via_csv(state="WA", list_type="main")
        assert records[0]["visa_190"] is True

    @patch("src.scrapers.wa_scraper.requests.get")
    def test_returns_empty_on_http_error(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        records = _scrape_via_csv(state="WA", list_type="main")
        assert records == []

    @patch("src.scrapers.wa_scraper.requests.get")
    def test_cleans_6digit_code_from_csv(self, mock_get):
        """Kode ANZSCO dengan spasi/prefix di-clean ke 6 digit."""
        csv_data = self._make_csv_response([
            {"ANZSCO Code": "Code: 261311", "Occupation": "Software Engineer"},
        ])
        mock_resp = MagicMock()
        mock_resp.text = csv_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        records = _scrape_via_csv(state="WA", list_type="main")
        assert records[0]["raw_code"] == "261311"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: scrape() — entry point dengan Selenium di-mock
# ═══════════════════════════════════════════════════════════════════════════════

class TestScrapeEntryPoint:
    """Menguji fungsi scrape() dengan semua I/O di-mock."""

    @patch("src.scrapers.wa_scraper._scrape_via_csv")
    @patch("src.scrapers.wa_scraper._scrape_via_selenium")
    def test_returns_selenium_records_when_available(self, mock_selenium, mock_csv):
        fake_records = [
            {"state": "WA", "list_type": "main", "raw_code": "261311",
             "raw_name": "Software Engineer", "visa_190": True, "visa_491": False}
        ]
        mock_selenium.return_value = fake_records
        mock_csv.return_value = []

        result = scrape("https://migration.wa.gov.au/fake", state="WA", list_type="main")
        assert result == fake_records
        mock_selenium.assert_called_once()
        mock_csv.assert_not_called()  # Tidak fallback jika selenium sukses

    @patch("src.scrapers.wa_scraper._scrape_via_csv")
    @patch("src.scrapers.wa_scraper._scrape_via_selenium")
    def test_falls_back_to_csv_when_selenium_empty(self, mock_selenium, mock_csv):
        csv_records = [
            {"state": "WA", "list_type": "main", "raw_code": "233211",
             "raw_name": "Civil Engineer", "visa_190": True, "visa_491": True}
        ]
        mock_selenium.return_value = []   # Selenium gagal / kosong
        mock_csv.return_value = csv_records

        result = scrape("https://migration.wa.gov.au/fake", state="WA", list_type="main")
        assert result == csv_records
        mock_csv.assert_called_once()

    @patch("src.scrapers.wa_scraper._scrape_via_csv")
    @patch("src.scrapers.wa_scraper._scrape_via_selenium")
    def test_returns_empty_when_both_fail(self, mock_selenium, mock_csv):
        mock_selenium.return_value = []
        mock_csv.return_value = []

        result = scrape("https://migration.wa.gov.au/fake", state="WA", list_type="main")
        assert result == []

    @patch("src.scrapers.wa_scraper._scrape_via_csv")
    @patch("src.scrapers.wa_scraper._scrape_via_selenium")
    def test_correct_state_and_listtype_passed(self, mock_selenium, mock_csv):
        mock_selenium.return_value = [{"dummy": True}]
        mock_csv.return_value = []

        scrape("https://migration.wa.gov.au/fake", state="WA", list_type="dama")
        call_args = mock_selenium.call_args
        assert call_args[0][1] == "WA"       # state
        assert call_args[0][2] == "dama"     # list_type
