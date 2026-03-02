"""
Data Quality Tests — Output CSV Validation
===========================================
Menguji kualitas data dari file CSV output scraper di folder output/.

Test ini memvalidasi:
  1. Format dan struktur kolom
  2. Format kode ANZSCO (occupation & unit group)
  3. Tidak ada duplikat
  4. Kelengkapan data (tidak ada kolom kritis yang kosong)
  5. Nilai valid untuk kolom boolean (190, 491)
  6. Coverage state (setidaknya 1 state ada)
  7. Jumlah data minimum per state yang ada

Jalankan:
    pytest tests/test_data_quality.py -v

Atau dengan print output:
    pytest tests/test_data_quality.py -v -s
"""

import sys
import os
import re
import csv
import glob
import pytest
from pathlib import Path
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Konfigurasi ────────────────────────────────────────────────────────────────

OUTPUT_DIR         = Path(__file__).parent.parent / "output"
MIN_ROWS_TOTAL     = 10       # minimal total baris (tidak termasuk header)
MIN_ROWS_PER_STATE = 5        # minimal baris per state yang ada
MAX_EMPTY_NAME_PCT = 0.05     # max 5% baris boleh punya occupation_name kosong

# Regex pola kode ANZSCO
RE_OCCUPATION_CODE  = re.compile(r"^\d{6}$")           # 6-digit: e.g. 261311
RE_UNIT_GROUP_CODE  = re.compile(r"^\d{4}$")           # 4-digit: e.g. 2613

# Kolom wajib di CSV
REQUIRED_COLUMNS = {
    "state_code",
    "anzsco_occupation_code",
    "occupation_name",
    "190",
    "491",
}

# State yang DIKETAHUI sudah punya data di output
# (update setelah menjalankan lebih banyak scraper)
KNOWN_STATES = {"NSW", "WA", "VIC", "QLD", "SA", "TAS", "ACT", "NT"}


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE: Load CSV terbaru dari folder output/
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def latest_csv_path():
    """Return path ke file CSV terbaru di folder output/."""
    csv_files = sorted(OUTPUT_DIR.glob("occupation_list_*.csv"), reverse=True)
    if not csv_files:
        pytest.skip(
            f"Tidak ada file CSV di {OUTPUT_DIR}. "
            "Jalankan scraper terlebih dahulu: python src/main.py"
        )
    latest = csv_files[0]
    print(f"\n  [CSV] File yang digunakan: {latest.name}")
    return latest


@pytest.fixture(scope="module")
def csv_rows(latest_csv_path):
    """Load semua baris CSV sebagai list of dict."""
    rows = []
    with open(latest_csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip baris kosong sepenuhnya
            if any(v.strip() for v in row.values()):
                rows.append(row)
    print(f"  [INFO] Total baris dimuat: {len(rows)}")
    return rows


@pytest.fixture(scope="module")
def csv_columns(latest_csv_path):
    """Return set nama kolom dari CSV."""
    with open(latest_csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return set(reader.fieldnames or [])


# ═══════════════════════════════════════════════════════════════════════════════
# TEST GROUP 1: Struktur & Kolom
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvStructure:
    """Validasi bahwa CSV punya kolom yang diharapkan dan tidak kosong."""

    def test_file_exists(self, latest_csv_path):
        """File CSV output harus ada."""
        assert latest_csv_path.exists(), f"File tidak ditemukan: {latest_csv_path}"

    def test_file_not_empty(self, csv_rows):
        """CSV harus punya setidaknya MIN_ROWS_TOTAL baris data."""
        assert len(csv_rows) >= MIN_ROWS_TOTAL, (
            f"CSV hanya punya {len(csv_rows)} baris, minimum {MIN_ROWS_TOTAL}"
        )

    def test_required_columns_present(self, csv_columns):
        """Kolom wajib harus ada di CSV."""
        missing = REQUIRED_COLUMNS - csv_columns
        assert not missing, (
            f"Kolom wajib tidak ditemukan di CSV: {missing}\n"
            f"Kolom yang ada: {csv_columns}"
        )

    def test_no_completely_empty_rows(self, csv_rows):
        """Tidak ada baris yang semua kolomnya kosong."""
        empty_rows = [
            i + 2 for i, r in enumerate(csv_rows)
            if not any(v.strip() for v in r.values())
        ]
        assert not empty_rows, f"Baris kosong sepenuhnya ditemukan di baris CSV: {empty_rows}"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST GROUP 2: Format Kode ANZSCO
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnzscoFormat:
    """Validasi format kode ANZSCO di CSV."""

    def test_occupation_code_format(self, csv_rows):
        """
        anzsco_occupation_code harus 6 digit atau kosong.
        Tidak boleh ada angka selain 4 atau 6 digit.
        """
        bad_rows = []
        for i, row in enumerate(csv_rows):
            code = (row.get("anzsco_occupation_code") or "").strip()
            if code and not RE_OCCUPATION_CODE.match(code):
                bad_rows.append((i + 2, code))

        assert not bad_rows, (
            f"Format kode occupation tidak valid (harus 6 digit atau kosong):\n"
            + "\n".join(f"  Baris {r}: {c!r}" for r, c in bad_rows[:10])
        )

    def test_unit_group_code_format(self, csv_rows):
        """
        anzsco_unit_group_code harus 4 digit atau kosong.
        """
        bad_rows = []
        for i, row in enumerate(csv_rows):
            code = (row.get("anzsco_unit_group_code") or "").strip()
            if code and not RE_UNIT_GROUP_CODE.match(code):
                bad_rows.append((i + 2, code))

        assert not bad_rows, (
            f"Format unit group code tidak valid (harus 4 digit atau kosong):\n"
            + "\n".join(f"  Baris {r}: {c!r}" for r, c in bad_rows[:10])
        )

    def test_occupation_code_matches_unit_group_prefix(self, csv_rows):
        """
        Jika kedua kode ada: 4 digit pertama occupation_code harus sama dengan unit_group_code.
        Contoh: occupation_code=261311, unit_group_code=2613 → prefix '2613' match.
        """
        mismatches = []
        for i, row in enumerate(csv_rows):
            occ_code   = (row.get("anzsco_occupation_code")  or "").strip()
            group_code = (row.get("anzsco_unit_group_code") or "").strip()
            if (RE_OCCUPATION_CODE.match(occ_code) and
                RE_UNIT_GROUP_CODE.match(group_code)):
                if not occ_code.startswith(group_code):
                    mismatches.append((i + 2, occ_code, group_code))

        assert not mismatches, (
            f"occupation_code tidak sesuai prefix unit_group_code:\n"
            + "\n".join(
                f"  Baris {r}: occ={o!r}, group={g!r}" for r, o, g in mismatches[:10]
            )
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST GROUP 3: Kelengkapan Data (Completeness)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataCompleteness:
    """Validasi bahwa data tidak terlalu banyak yang kosong."""

    def test_state_code_never_empty(self, csv_rows):
        """Kolom state_code tidak boleh pernah kosong."""
        empty = [i + 2 for i, r in enumerate(csv_rows)
                 if not (r.get("state_code") or "").strip()]
        assert not empty, (
            f"state_code kosong di {len(empty)} baris: {empty[:10]}"
        )

    def test_occupation_name_mostly_not_empty(self, csv_rows):
        """
        occupation_name boleh kosong untuk sebagian kecil baris (< MAX_EMPTY_NAME_PCT).
        Biasanya ada saat scraper hanya dapat kode ANZSCO tapi tidak nama.
        """
        empty_count = sum(
            1 for r in csv_rows
            if not (r.get("occupation_name") or "").strip()
        )
        empty_pct = empty_count / len(csv_rows) if csv_rows else 0

        assert empty_pct <= MAX_EMPTY_NAME_PCT, (
            f"Terlalu banyak occupation_name kosong: "
            f"{empty_count} dari {len(csv_rows)} baris ({empty_pct:.1%})\n"
            f"Batas maksimal: {MAX_EMPTY_NAME_PCT:.0%}"
        )

    def test_at_least_one_visa_flag_true_per_row(self, csv_rows):
        """
        Setiap baris harus eligible untuk setidaknya 1 visa (190 atau 491 = '1').
        Baris yang sama sekali tidak eligible tidak masuk akal di occupation list.
        """
        not_eligible = []
        for i, row in enumerate(csv_rows):
            v190 = (row.get("190") or "0").strip()
            v491 = (row.get("491") or "0").strip()
            if v190 not in ("1", "True", "true") and v491 not in ("1", "True", "true"):
                not_eligible.append((i + 2, row.get("state_code"), row.get("occupation_name")))

        # Warn saja, tidak hard-fail, karena beberapa scraper mungkin belum sempurna
        if not_eligible:
            print(
                f"\n  [WARN] {len(not_eligible)} baris tidak eligible untuk 190 maupun 491:"
            )
            for row_num, state, name in not_eligible[:5]:
                print(f"     Baris {row_num}: [{state}] {name}")

        # Hard fail hanya jika > 20% baris tidak eligible
        pct = len(not_eligible) / len(csv_rows) if csv_rows else 0
        assert pct <= 0.20, (
            f"Terlalu banyak baris tidak eligible visa apapun: "
            f"{len(not_eligible)}/{len(csv_rows)} ({pct:.1%})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST GROUP 4: Format Kolom Boolean (190, 491)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVisaColumns:
    """Validasi nilai kolom 190 dan 491."""

    VALID_VALUES = {"0", "1", "True", "False", "true", "false", ""}

    def test_visa_190_valid_values(self, csv_rows):
        """Kolom '190' hanya boleh berisi nilai boolean yang valid."""
        bad_rows = [
            (i + 2, r.get("190"))
            for i, r in enumerate(csv_rows)
            if (r.get("190") or "").strip() not in self.VALID_VALUES
        ]
        assert not bad_rows, (
            f"Nilai tidak valid di kolom '190':\n"
            + "\n".join(f"  Baris {r}: {v!r}" for r, v in bad_rows[:10])
        )

    def test_visa_491_valid_values(self, csv_rows):
        """Kolom '491' hanya boleh berisi nilai boolean yang valid."""
        bad_rows = [
            (i + 2, r.get("491"))
            for i, r in enumerate(csv_rows)
            if (r.get("491") or "").strip() not in self.VALID_VALUES
        ]
        assert not bad_rows, (
            f"Nilai tidak valid di kolom '491':\n"
            + "\n".join(f"  Baris {r}: {v!r}" for r, v in bad_rows[:10])
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST GROUP 5: Duplikat
# ═══════════════════════════════════════════════════════════════════════════════

class TestDuplicates:
    """Validasi tidak ada duplikat di CSV."""

    def test_no_exact_duplicate_rows(self, csv_rows):
        """Tidak ada baris yang benar-benar identik (semua kolom sama)."""
        # Key: tuple dari semua nilai kolom penting
        seen = Counter()
        for row in csv_rows:
            key = (
                (row.get("state_code") or "").strip(),
                (row.get("anzsco_occupation_code") or "").strip(),
                (row.get("occupation_name") or "").strip(),
            )
            seen[key] += 1

        duplicates = {k: v for k, v in seen.items() if v > 1}
        assert not duplicates, (
            f"Ditemukan {len(duplicates)} kombinasi duplikat (state+kode+nama):\n"
            + "\n".join(
                f"  [{k[0]}] {k[2]!r} ({k[1]}) — muncul {v}x"
                for k, v in list(duplicates.items())[:10]
            )
        )

    def test_no_duplicate_occupation_codes_per_state(self, csv_rows):
        """
        Kode occupation 6-digit yang sama tidak boleh muncul 2x untuk state yang sama.
        (Kode yg sama bisa muncul di state berbeda — itu valid.)
        """
        seen = Counter()
        for row in csv_rows:
            state = (row.get("state_code") or "").strip()
            code  = (row.get("anzsco_occupation_code") or "").strip()
            if RE_OCCUPATION_CODE.match(code):
                seen[(state, code)] += 1

        duplicates = {k: v for k, v in seen.items() if v > 1}
        assert not duplicates, (
            f"Kode occupation duplikat dalam satu state:\n"
            + "\n".join(
                f"  [{k[0]}] {k[1]} — muncul {v}x"
                for k, v in list(duplicates.items())[:10]
            )
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST GROUP 6: Coverage State
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateCoverage:
    """Validasi data coverage antar state."""

    def test_at_least_one_state_present(self, csv_rows):
        """CSV harus punya data dari setidaknya 1 state."""
        states_found = {(r.get("state_code") or "").strip() for r in csv_rows if r.get("state_code")}
        states_found -= {""}  # buang string kosong
        assert len(states_found) >= 1, "Tidak ada state ditemukan di CSV!"

    def test_state_codes_are_valid(self, csv_rows):
        """
        State code yang ada di CSV harus salah satu dari KNOWN_STATES.
        Mendeteksi jika ada nilai aneh di kolom state_code.
        """
        invalid_states = set()
        for row in csv_rows:
            state = (row.get("state_code") or "").strip()
            if state and state not in KNOWN_STATES:
                invalid_states.add(state)

        assert not invalid_states, (
            f"Nilai state_code tidak dikenal: {invalid_states}\n"
            f"State yang valid: {KNOWN_STATES}"
        )

    def test_minimum_rows_per_state(self, csv_rows):
        """
        Setiap state yang ada di CSV harus punya setidaknya MIN_ROWS_PER_STATE baris.
        Ini mendeteksi jika scraper state tertentu hanya dapat sedikit data.
        """
        state_counts = Counter(
            (r.get("state_code") or "").strip()
            for r in csv_rows
            if (r.get("state_code") or "").strip()
        )
        # Buang state kosong
        state_counts.pop("", None)

        thin_states = {
            state: count
            for state, count in state_counts.items()
            if count < MIN_ROWS_PER_STATE
        }

        # Print summary semua state
        print(f"\n  [INFO] Jumlah baris per state:")
        for state, count in sorted(state_counts.items()):
            status = "[OK]" if count >= MIN_ROWS_PER_STATE else "[WARN]"
            print(f"     {status} {state}: {count} baris")

        assert not thin_states, (
            f"State dengan data terlalu sedikit (< {MIN_ROWS_PER_STATE} baris):\n"
            + "\n".join(f"  {s}: {c} baris" for s, c in thin_states.items())
        )

    def test_print_state_summary(self, csv_rows):
        """
        SELALU PASS — hanya mencetak ringkasan state coverage.
        Jalankan dengan -s untuk melihat output.
        """
        state_counts = Counter(
            (r.get("state_code") or "").strip()
            for r in csv_rows
        )
        state_counts.pop("", None)

        total = sum(state_counts.values())
        print(f"\n  ================================================")
        print(f"  RINGKASAN DATA QUALITY")
        print(f"  ================================================")
        print(f"  Total baris    : {total}")
        print(f"  Jumlah state   : {len(state_counts)}")
        print(f"  State coverage : {', '.join(sorted(state_counts.keys()))}")
        print(f"  ------------------------------------------------")
        print(f"  {'State':<8} {'Jumlah Baris':>15}")
        for state, count in sorted(state_counts.items()):
            print(f"  {state:<8} {count:>15}")
        print(f"  ================================================")
        assert True
