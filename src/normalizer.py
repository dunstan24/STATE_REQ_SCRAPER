"""
Normalizer — Stage 2 of the occupation scraper pipeline.

Matches raw scraped records (which may contain partial ANZSCO codes or names)
against the ANZSCO 2022 master CSV to produce the final normalized output:

    state_code | anzsco_unit_group_code | unit_group_name |
    anzsco_occupation_code | occupation_name | 190 | 491

Matching strategy (in order):
  1. 6-digit raw_code → direct match on `occupation_code`
       └─ FALLBACK jika tidak ketemu (e.g. kode ANZSCO 2013 yang tidak ada di 2022):
          1a. name match DULU (lebih akurat, overwrite code dengan referensi master)
              - exact match pada occupation_title
              - exact match pada unit_group_title
              - partial / best-similarity match pada occupation_title
              - partial / best-similarity match pada unit_group_title
          1b. BARU 4-digit prefix → expand semua occupations dalam unit_group
              (hanya jika name matching gagal total)
  2. 4-digit raw_code → expand to all occupations under that `unit_group_code`
  3. raw_name only   → fuzzy case-insensitive match on `occupation_title`

CATATAN PENTING — Kode ANZSCO 2013 vs 2022:
  Beberapa state masih menggunakan kode ANZSCO 2013 pada occupation list mereka.
  Ketika 6-digit code tidak ditemukan di master 2022, normalizer TIDAK langsung
  expand ke unit_group (strategi lama yang rawan mismatch). Sebaliknya:
    - Jika raw_name tersedia → coba name matching dulu, gunakan kode dari MASTER
    - Jika name matching gagal → baru fallback ke unit_group expansion
    - Jika semua gagal → simpan sebagai unmatched untuk review manual

CHANGELOG:
  2026-02-27 (fix-fallback-order):
    Urutan fallback untuk 6-digit code yang tidak ada di master diubah:
    SEBELUM: 1a=unit_group_prefix → 1b-1e=name_matching
    SESUDAH: 1a=name_matching (lebih akurat) → 1b=unit_group_prefix (last resort)

    Alasan: Fallback unit_group expansion tanpa verifikasi nama menyebabkan
    occupation_code prefix tidak cocok dengan unit_group_code yang di-assign
    (e.g. Poultry Farmer 121321 ter-assign ke group 1220 bukan 1213).
    Name matching menggunakan data dari master sehingga kode yang dihasilkan
    selalu konsisten.

  2026-02-26 (fix-dedup):
    Deduplicate logic changed to groupby(state, occ_code) + max() on visa flags.

  2026-02-26 (fallback-matching):
    Added multi-step fallback for 6-digit codes not found in master.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def load_master(master_path: str) -> pd.DataFrame:
    """
    Load the ANZSCO 2022 master CSV.
    Returns a cleaned DataFrame with consistent column types.

    Menggunakan engine='python' dan on_bad_lines='warn' agar skrip tidak mati
    jika menemukan baris cacat di dalam file CSV master.
    """
    df = pd.read_csv(
        master_path,
        dtype=str,
        engine='python',
        on_bad_lines='warn'
    )

    for col in df.columns:
        df[col] = df[col].str.strip()

    if "occupation_code" in df.columns:
        df["occupation_code"] = df["occupation_code"].str.zfill(6)
    if "unit_group_code" in df.columns:
        df["unit_group_code"] = df["unit_group_code"].str.zfill(4)

    logger.info(f"Loaded master data: {len(df)} rows from {master_path}")
    return df


def normalize(raw_records: List[dict], master_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a list of raw scraper records against the master ANZSCO data.

    Parameters
    ----------
    raw_records : list of dict
        Each dict must have keys: state, raw_code, raw_name,
        visa_190 (bool), visa_491 (bool).
    master_df : pd.DataFrame
        Loaded ANZSCO 2022 master CSV (from load_master()).

    Returns
    -------
    pd.DataFrame with columns:
        state_code, anzsco_unit_group_code, unit_group_name,
        anzsco_occupation_code, occupation_name, 190, 491
    """
    output_rows = []

    occ_by_code = master_df.set_index("occupation_code")
    ug_by_code  = master_df.groupby("unit_group_code")

    name_lookup = master_df.copy()
    name_lookup["_occ_lower"] = name_lookup["occupation_title"].str.lower()
    name_lookup["_ug_lower"]  = name_lookup["unit_group_title"].str.lower()

    for rec in raw_records:
        state    = rec.get("state", "")
        raw_code = (rec.get("raw_code") or "").strip()
        raw_name = (rec.get("raw_name") or "").strip()
        visa_190 = int(bool(rec.get("visa_190", False)))
        visa_491 = int(bool(rec.get("visa_491", False)))

        matched_rows = _find_matches(
            raw_code, raw_name, occ_by_code, ug_by_code, name_lookup, master_df
        )

        if matched_rows is not None and len(matched_rows) > 0:
            for _, mrow in matched_rows.iterrows():
                # OVERWRITE ABSOLUT: kode dan nama selalu dari master data
                # Kode ANZSCO 2013 dari scraper akan digantikan oleh kode 2022
                output_rows.append({
                    "state_code":             state,
                    "anzsco_unit_group_code": mrow["unit_group_code"],
                    "unit_group_name":        mrow["unit_group_title"],
                    "anzsco_occupation_code": mrow["occupation_code"],
                    "occupation_name":        mrow["occupation_title"],
                    "190":                    visa_190,
                    "491":                    visa_491,
                })
        else:
            logger.debug(
                f"No master match for raw_code={raw_code!r}, raw_name={raw_name!r}"
            )
            output_rows.append({
                "state_code":             state,
                "anzsco_unit_group_code": None,
                "unit_group_name":        None,
                "anzsco_occupation_code": raw_code if raw_code else None,
                "occupation_name":        raw_name if raw_name else None,
                "190":                    visa_190,
                "491":                    visa_491,
            })

    if not output_rows:
        return pd.DataFrame(columns=[
            "state_code", "anzsco_unit_group_code", "unit_group_name",
            "anzsco_occupation_code", "occupation_name", "190", "491"
        ])

    result = pd.DataFrame(output_rows)
    result = _deduplicate_with_visa_merge(result)
    result = result.reset_index(drop=True)

    return result


# ---------------------------------------------------------------------------
# Matching core
# ---------------------------------------------------------------------------

def _find_matches(
    raw_code: str,
    raw_name: str,
    occ_by_code,
    ug_by_code,
    name_lookup: pd.DataFrame,
    master_df: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """
    Cari baris yang cocok di master data.
    Returns DataFrame slice (1 atau lebih baris) atau None.

    Matching priority:
      1. 6-digit occupation code   → exact 1 row (direct hit)
           └─ jika tidak ada di master (kode ANZSCO 2013 deprecated):
              1a. name matching DULU — kode dari master yang dipakai (AKURAT)
                  i.   exact occ title
                  ii.  exact ug title → expand semua occ dalam group
                  iii. partial occ title → BEST single match
                  iv.  partial ug title  → BEST matching group's occupations
              1b. 4-digit prefix → expand unit_group (LAST RESORT)
                  Hanya jika name matching gagal total. Hasilnya lebih kasar
                  tapi masih lebih baik dari unmatched.
      2. 4-digit unit group code   → semua occ dalam group
      3. raw_name only             → name matching hierarchy sama seperti 1a
    """

    # ── 1. 6-digit occupation code ─────────────────────────────────────────
    if re.fullmatch(r"\d{6}", raw_code):
        padded = raw_code.zfill(6)

        if padded in occ_by_code.index:
            # Direct hit — return langsung, paling akurat
            return occ_by_code.loc[[padded]].reset_index()

        # Kode tidak ada di master 2022 (kemungkinan kode ANZSCO 2013)
        logger.debug(
            f"6-digit code {padded} not in master 2022 — "
            f"attempting fallback (raw_name={raw_name!r})"
        )

        # ── 1a. Name matching DULU ────────────────────────────────────────
        # Ini adalah perubahan utama dari versi sebelumnya.
        # Dengan name matching, kode yang dihasilkan selalu dari master 2022
        # sehingga occupation_code dan unit_group_code SELALU konsisten.
        # Tidak perlu validasi prefix mismatch lagi.
        if raw_name:
            name_result = _match_by_name(raw_name, name_lookup)
            if name_result is not None:
                master_code = name_result["occupation_code"].iloc[0]
                logger.info(
                    f"  [Fallback 1a — name] {padded} (ANZSCO 2013) → "
                    f"matched via name {raw_name!r} → "
                    f"master 2022 code {master_code}"
                )
                return name_result

        # ── 1b. Unit group prefix (last resort) ───────────────────────────
        # Dipakai hanya jika name matching gagal total (raw_name kosong
        # atau tidak ada kecocokan sama sekali di master).
        ug_prefix = padded[:4]
        if ug_prefix in ug_by_code.groups:
            group = ug_by_code.get_group(ug_prefix)
            logger.info(
                f"  [Fallback 1b — unit_group] {padded} → "
                f"expanded to unit_group {ug_prefix} "
                f"({len(group)} occupations)"
            )
            return group.reset_index(drop=True)

        # Semua fallback habis — simpan sebagai unmatched
        logger.warning(
            f"No match found for 6-digit code {padded} "
            f"(raw_name={raw_name!r}) — will be kept as unmatched."
        )
        return None

    # ── 2. 4-digit unit group code ─────────────────────────────────────────
    if re.fullmatch(r"\d{4}", raw_code):
        padded = raw_code.zfill(4)
        if padded in ug_by_code.groups:
            return ug_by_code.get_group(padded).reset_index(drop=True)
        logger.debug(f"4-digit unit group code {padded} not in master data.")

    # ── 3. Name-only matching ──────────────────────────────────────────────
    if raw_name:
        return _match_by_name(raw_name, name_lookup)

    return None


def _match_by_name(
    raw_name: str,
    name_lookup: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """
    Cari baris master menggunakan name-based matching.

    Priority:
      a. Exact match pada occupation_title  → 1 row
      b. Exact match pada unit_group_title  → semua occ dalam group
      c. Partial match pada occupation_title → BEST single match by similarity
      d. Partial match pada unit_group_title → BEST matching group's occupations

    Returns DataFrame slice atau None.
    """
    name_lower = raw_name.lower()
    drop_cols  = ["_occ_lower", "_ug_lower"]

    # a. Exact occupation title
    exact_occ = name_lookup[name_lookup["_occ_lower"] == name_lower]
    if not exact_occ.empty:
        return exact_occ.drop(columns=drop_cols).reset_index(drop=True)

    # b. Exact unit_group title → expand semua occupation dalam group
    exact_ug = name_lookup[name_lookup["_ug_lower"] == name_lower]
    if not exact_ug.empty:
        return exact_ug.drop(columns=drop_cols).reset_index(drop=True)

    # c. Partial occupation title — BEST single match only
    partial_occ = name_lookup[
        name_lookup["_occ_lower"].str.contains(re.escape(name_lower), na=False)
    ]
    if not partial_occ.empty:
        best_idx = _best_match_index(partial_occ["_occ_lower"], name_lower)
        best_row = partial_occ.iloc[[best_idx]].drop(columns=drop_cols)
        return best_row.reset_index(drop=True)

    # d. Partial unit_group title — BEST matching group's occupations
    partial_ug = name_lookup[
        name_lookup["_ug_lower"].str.contains(re.escape(name_lower), na=False)
    ]
    if not partial_ug.empty:
        best_idx     = _best_match_index(partial_ug["_ug_lower"], name_lower)
        best_ug_code = partial_ug.iloc[best_idx]["unit_group_code"]
        group_rows   = partial_ug[partial_ug["unit_group_code"] == best_ug_code]
        return group_rows.drop(columns=drop_cols).reset_index(drop=True)

    return None


def _best_match_index(series: pd.Series, query: str) -> int:
    """
    Return posisi (bukan label) dari best match di `series`
    menggunakan SequenceMatcher similarity ratio.
    """
    best_score = -1.0
    best_pos   = 0
    for pos, candidate in enumerate(series):
        score = SequenceMatcher(None, query, str(candidate)).ratio()
        if score > best_score:
            best_score = score
            best_pos   = pos
    return best_pos


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate_with_visa_merge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate rows per (state_code, anzsco_occupation_code).
    Visa flags digabung dengan OR logic (max) — jika satu record eligible,
    maka hasil akhir eligible.
    """
    has_code  = df["anzsco_occupation_code"].notna()
    matched   = df[has_code].copy()
    unmatched = df[~has_code].copy()

    if not matched.empty:
        desc_cols = ["anzsco_unit_group_code", "unit_group_name", "occupation_name"]

        first_vals = (
            matched
            .groupby(["state_code", "anzsco_occupation_code"], sort=False)[desc_cols]
            .first()
        )
        visa_vals = (
            matched
            .groupby(["state_code", "anzsco_occupation_code"], sort=False)[["190", "491"]]
            .max()
        )
        merged = first_vals.join(visa_vals).reset_index()

        original_flags = (
            matched
            .groupby(["state_code", "anzsco_occupation_code"])[["190", "491"]]
            .first()
        )
        upgraded = merged.set_index(["state_code", "anzsco_occupation_code"])[["190", "491"]]
        diff = upgraded.ne(original_flags).any(axis=1)
        if diff.any():
            for idx in diff[diff].index:
                state, code = idx
                orig = original_flags.loc[idx]
                new  = upgraded.loc[idx]
                logger.debug(
                    f"[Dedup] Merged visa flags for [{state}] {code}: "
                    f"190: {orig['190']}→{new['190']}, "
                    f"491: {orig['491']}→{new['491']}"
                )
        matched = merged

    if not unmatched.empty:
        unmatched = unmatched.drop_duplicates(subset=["state_code", "occupation_name"])

    return pd.concat([matched, unmatched], ignore_index=True)