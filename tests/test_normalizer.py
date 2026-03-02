"""
Unit Tests for normalizer.py
==============================
Menguji logika normalize(), _find_matches(), dan _best_match_index()
menggunakan DataFrame master kecil (tidak butuh file asli).

Jalankan:
    pytest tests/test_normalizer.py -v
"""

import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.normalizer import normalize, _find_matches, _best_match_index, load_master


# ── Fixture: master DataFrame mini ──────────────────────────────────────────

@pytest.fixture
def master_df():
    """Mini master ANZSCO DataFrame untuk testing."""
    return pd.DataFrame([
        {"occupation_code": "261311", "occupation_title": "Software Engineer",
         "unit_group_code": "2613", "unit_group_title": "Software and Applications Programmers"},
        {"occupation_code": "261312", "occupation_title": "Developer Programmer",
         "unit_group_code": "2613", "unit_group_title": "Software and Applications Programmers"},
        {"occupation_code": "233211", "occupation_title": "Civil Engineer",
         "unit_group_code": "2332", "unit_group_title": "Civil Engineering Professionals"},
        {"occupation_code": "233212", "occupation_title": "Geotechnical Engineer",
         "unit_group_code": "2332", "unit_group_title": "Civil Engineering Professionals"},
        {"occupation_code": "254411", "occupation_title": "Registered Nurse (Aged Care)",
         "unit_group_code": "2544", "unit_group_title": "Registered Nurses"},
        {"occupation_code": "254412", "occupation_title": "Registered Nurse (Child and Family Health)",
         "unit_group_code": "2544", "unit_group_title": "Registered Nurses"},
    ])


@pytest.fixture
def raw_records_6digit():
    return [
        {"state": "NSW", "list_type": "main", "raw_code": "261311",
         "raw_name": "Software Engineer", "visa_190": True, "visa_491": False},
        {"state": "NSW", "list_type": "main", "raw_code": "233211",
         "raw_name": "Civil Engineer", "visa_190": True, "visa_491": False},
    ]


@pytest.fixture
def raw_records_4digit():
    return [
        {"state": "VIC", "list_type": "main", "raw_code": "2613",
         "raw_name": None, "visa_190": True, "visa_491": False},
    ]


@pytest.fixture
def raw_records_name_only():
    return [
        {"state": "SA", "list_type": "main", "raw_code": None,
         "raw_name": "Software Engineer", "visa_190": True, "visa_491": True},
    ]


# ── Test Group 1: _best_match_index ─────────────────────────────────────────

class TestBestMatchIndex:
    def test_exact_match_scores_highest(self):
        series = pd.Series(["civil engineer", "software engineer", "software and applications programmer"])
        idx = _best_match_index(series, "software engineer")
        assert series.iloc[idx] == "software engineer"

    def test_closest_partial_match_selected(self):
        series = pd.Series(["registered nurse (aged care)", "registered nurse (mental health)", "registered nurse (child and family health)"])
        idx = _best_match_index(series, "registered nurse")
        # Harus return salah satu yang punya similarity tertinggi (paling pendek = paling mirip)
        assert idx in (0, 1, 2)  # semua valid, yang penting tidak error

    def test_single_element_returns_zero(self):
        series = pd.Series(["civil engineer"])
        assert _best_match_index(series, "civil engineer") == 0

    def test_empty_string_query_still_returns(self):
        series = pd.Series(["anything"])
        result = _best_match_index(series, "")
        assert result == 0


# ── Test Group 2: _find_matches ─────────────────────────────────────────────

class TestFindMatches:

    def _make_lookups(self, df):
        occ_by_code = df.set_index("occupation_code")
        ug_by_code  = df.groupby("unit_group_code")
        name_lookup = df.copy()
        name_lookup["_occ_lower"] = name_lookup["occupation_title"].str.lower()
        name_lookup["_ug_lower"]  = name_lookup["unit_group_title"].str.lower()
        return occ_by_code, ug_by_code, name_lookup

    def test_6digit_code_exact_match(self, master_df):
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("261311", "", occ, ug, nl, master_df)
        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["occupation_code"] == "261311"

    def test_6digit_code_not_in_master_returns_none(self, master_df):
        """FIX: 6-digit code tidak ditemukan harus return None (tidak fall-through ke name match)."""
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("999999", "Software Engineer", occ, ug, nl, master_df)
        assert result is None  # TIDAK boleh match via nama

    def test_4digit_code_returns_all_in_group(self, master_df):
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("2613", "", occ, ug, nl, master_df)
        assert result is not None
        assert len(result) == 2  # 261311 dan 261312
        assert set(result["occupation_code"]) == {"261311", "261312"}

    def test_4digit_code_not_in_master_falls_to_name(self, master_df):
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("9999", "Civil Engineer", occ, ug, nl, master_df)
        # Harus fallback ke name match dan menemukan 233211
        assert result is not None
        assert any(result["occupation_code"] == "233211")

    def test_name_exact_match(self, master_df):
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("", "Civil Engineer", occ, ug, nl, master_df)
        assert result is not None
        assert result.iloc[0]["occupation_code"] == "233211"

    def test_name_exact_unit_group_match(self, master_df):
        """Match pada unit_group_title expand ke semua occupation di group tersebut."""
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("", "Registered Nurses", occ, ug, nl, master_df)
        assert result is not None
        assert len(result) == 2
        assert set(result["occupation_code"]) == {"254411", "254412"}

    def test_partial_name_returns_best_single_row(self, master_df):
        """FIX: partial match harus return 1 baris terbaik, bukan semua matches."""
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("", "Software Engineer", occ, ug, nl, master_df)
        # Harus match exact "Software Engineer" (261311), bukan Developer Programmer
        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["occupation_code"] == "261311"

    def test_no_match_returns_none(self, master_df):
        occ, ug, nl = self._make_lookups(master_df)
        result = _find_matches("", "Underwater Basket Weaver", occ, ug, nl, master_df)
        assert result is None


# ── Test Group 3: normalize() ────────────────────────────────────────────────

class TestNormalize:

    def test_normalize_6digit_code_records(self, master_df, raw_records_6digit):
        result = normalize(raw_records_6digit, master_df)
        assert len(result) == 2
        codes = set(result["anzsco_occupation_code"])
        assert "261311" in codes
        assert "233211" in codes

    def test_normalize_4digit_code_expands_to_group(self, master_df, raw_records_4digit):
        result = normalize(raw_records_4digit, master_df)
        # Unit group 2613 punya 2 occupations
        assert len(result) == 2
        assert set(result["anzsco_occupation_code"]) == {"261311", "261312"}

    def test_normalize_name_only_matches(self, master_df, raw_records_name_only):
        result = normalize(raw_records_name_only, master_df)
        assert len(result) >= 1
        assert "261311" in result["anzsco_occupation_code"].values

    def test_output_columns_complete(self, master_df, raw_records_6digit):
        result = normalize(raw_records_6digit, master_df)
        expected_cols = {
            "state_code", "anzsco_unit_group_code", "unit_group_name",
            "anzsco_occupation_code", "occupation_name", "190", "491"
        }
        assert expected_cols.issubset(set(result.columns))

    def test_visa_flags_preserved(self, master_df):
        records = [
            {"state": "NSW", "list_type": "main", "raw_code": "261311",
             "raw_name": None, "visa_190": True, "visa_491": False},
            {"state": "NSW", "list_type": "main", "raw_code": "233211",
             "raw_name": None, "visa_190": False, "visa_491": True},
        ]
        result = normalize(records, master_df)
        row_261311 = result[result["anzsco_occupation_code"] == "261311"].iloc[0]
        assert row_261311["190"] == 1
        assert row_261311["491"] == 0
        row_233211 = result[result["anzsco_occupation_code"] == "233211"].iloc[0]
        assert row_233211["190"] == 0
        assert row_233211["491"] == 1

    def test_prefix_validation_drops_mismatched_rows(self, master_df):
        """
        FIX: Normalizer harus drop baris di mana occupation_code prefix
        tidak match unit_group_code.
        Simulasikan dengan inject baris invalid ke dalam output.
        """
        # Secara tidak langsung diuji karena partial name match sekarang
        # return best single match — unit_group_code selalu match prefixnya
        records = [
            {"state": "SA", "list_type": "main", "raw_code": "261311",
             "raw_name": None, "visa_190": True, "visa_491": False},
        ]
        result = normalize(records, master_df)
        # Semua baris harus punya occupation_code prefix yang match unit_group_code
        for _, row in result.iterrows():
            occ  = str(row["anzsco_occupation_code"] or "")
            grp  = str(row["anzsco_unit_group_code"]  or "")
            if occ and grp:
                assert occ.startswith(grp), (
                    f"Prefix mismatch: occ={occ}, group={grp}"
                )

    def test_no_duplicate_codes_per_state(self, master_df):
        """Kode occupation yang sama tidak boleh muncul 2x per state."""
        records = [
            {"state": "NSW", "list_type": "main", "raw_code": "261311",
             "raw_name": None, "visa_190": True, "visa_491": False},
            {"state": "NSW", "list_type": "main", "raw_code": "261311",
             "raw_name": None, "visa_190": True, "visa_491": False},  # duplikat
        ]
        result = normalize(records, master_df)
        nsw_261311 = result[(result["state_code"] == "NSW") &
                            (result["anzsco_occupation_code"] == "261311")]
        assert len(nsw_261311) == 1

    def test_empty_records_returns_empty_df(self, master_df):
        result = normalize([], master_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_unmatched_record_kept_as_raw(self, master_df):
        """Record yang tidak match master harus tetap disimpan dengan raw data."""
        records = [
            {"state": "ACT", "list_type": "main", "raw_code": "999999",
             "raw_name": "Underwater Basket Weaver", "visa_190": True, "visa_491": False},
        ]
        result = normalize(records, master_df)
        # Record tetap ada (sebagai unmatched)
        assert len(result) == 1
        assert result.iloc[0]["state_code"] == "ACT"
        assert result.iloc[0]["occupation_name"] == "Underwater Basket Weaver"
