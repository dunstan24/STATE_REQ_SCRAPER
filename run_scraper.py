"""
run_scraper.py — Entry point for the Occupation List Multi-State Scraper.

Usage:
    python run_scraper.py                          # Run all states
    python run_scraper.py --state QLD              # Run specific state only
    python run_scraper.py --no-headless            # Show browser window (diabaikan untuk ACT)
    python run_scraper.py --state SA --no-headless # State + visible browser
    python run_scraper.py --skip-normalize         # Output raw data without normalizing

Strategi penyimpanan:
    - Setiap state di-export langsung ke CSV begitu selesai (data aman meski crash di tengah)
    - Semua state digabung dan di-export ke XLSX di akhir run
    - Output diorganisir per folder run: outputs/run_YYYYMMDD_HHMM/
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Project paths ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    TARGET_URLS,
    MASTER_DATA_PATH,
    OUTPUT_DIR,
    LOG_DIR,
    LOG_LEVEL,
    LOG_FORMAT,
    TIMESTAMP_FORMAT,
)
from src.scrapers import get_scraper
from src.normalizer import load_master, normalize


# ── Logging setup ──────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
log_file  = os.path.join(LOG_DIR, f"scraper_{timestamp}.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _save_state_batch(
    records: list[dict],
    state: str,
    list_type: str,
    run_dir: Path,
) -> Path:
    """
    Simpan hasil scrape satu state langsung ke CSV.
    Dipanggil segera setelah tiap state selesai — data aman meski run berikutnya crash.

    Returns path file yang disimpan.
    """
    filename = f"{state}_{list_type}_raw.csv"
    path     = run_dir / filename
    df       = pd.DataFrame(records)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info(f"[Batch] Saved {len(records)} records → {path}")
    return path


def _merge_and_export(
    run_dir: Path,
    skip_normalize: bool,
    timestamp: str,
) -> None:
    """
    Baca semua CSV per-state di run_dir, merge, normalize (opsional),
    lalu export ke CSV + XLSX final.
    Dipanggil di akhir run setelah semua state selesai.
    """
    csv_files = sorted(run_dir.glob("*_raw.csv"))

    if not csv_files:
        logger.warning("[Merge] Tidak ada file batch CSV untuk di-merge.")
        return

    logger.info(f"[Merge] Menggabungkan {len(csv_files)} file batch...")
    # dtype str pada raw_code mencegah pandas auto-convert ke int
    # (misal "261111" → 261111) yang menyebabkan normalizer crash
    df_all = pd.concat(
        [pd.read_csv(f, dtype={"raw_code": str, "unit_group_code": str}) for f in csv_files],
        ignore_index=True,
    )
    logger.info(f"[Merge] Total {len(df_all)} records dari semua state.")

    if skip_normalize:
        df_out = df_all
        prefix = "raw_occupation_list"
    else:
        logger.info("[Merge] Memuat master ANZSCO untuk normalisasi...")
        try:
            master_df = load_master(MASTER_DATA_PATH)
        except FileNotFoundError:
            logger.error(f"[Merge] Master data tidak ditemukan: {MASTER_DATA_PATH}")
            logger.warning("[Merge] Melanjutkan export tanpa normalisasi.")
            df_out = df_all
            prefix = "raw_occupation_list"
        else:
            df_out = normalize(df_all.to_dict("records"), master_df)
            prefix = "occupation_list"
            logger.info(f"[Merge] Normalisasi selesai. {len(df_out)} output rows.")

    # Export final ke run_dir yang sama
    final_csv   = run_dir / f"{prefix}_FINAL_{timestamp}.csv"
    final_xlsx  = run_dir / f"{prefix}_FINAL_{timestamp}.xlsx"

    df_out.to_csv(final_csv, index=False, encoding="utf-8-sig")
    logger.info(f"[Merge] CSV final: {final_csv}")

    with pd.ExcelWriter(final_xlsx, engine="openpyxl") as writer:
        df_out.to_excel(writer, sheet_name="Occupation List", index=False)
    logger.info(f"[Merge] XLSX final: {final_xlsx}")

    return df_out, final_csv, final_xlsx


# ── Args ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Occupation List Multi-State Scraper")
    parser.add_argument(
        "--state", "-s",
        type=str, default=None,
        help="Scrape state tertentu saja (e.g. QLD, SA, NSW). Default: semua state."
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Jalankan browser dalam mode visible. (Diabaikan untuk ACT — selalu non-headless.)"
    )
    parser.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Export raw data tanpa normalisasi terhadap master ANZSCO."
    )
    return parser.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

def run(args):
    headless     = not args.no_headless
    state_filter = args.state.upper() if args.state else None

    # Filter target berdasarkan --state jika ada
    targets = TARGET_URLS
    if state_filter:
        targets = [t for t in TARGET_URLS if t["state"].upper() == state_filter]
        if not targets:
            logger.error(f"Tidak ada URL yang dikonfigurasi untuk state: {state_filter}")
            sys.exit(1)

    # Buat folder run khusus untuk run ini
    run_dir = Path(OUTPUT_DIR) / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output folder: {run_dir}")
    logger.info(f"Memulai scrape untuk {len(targets)} URL. Headless={headless}")

    # ── Stage 1: Scrape per state ──────────────────────────────────────────────
    success_states: list[str] = []
    failed_states:  list[str] = []

    for target in targets:
        state     = target["state"]
        list_type = target["list_type"]
        url       = target["url"]
        label     = f"{state} | {list_type}"

        logger.info(f"--- [{label}] ---")

        try:
            scraper_fn  = get_scraper(state)
            raw_records = scraper_fn(
                url=url,
                state=state,
                list_type=list_type,
                headless=headless,
            )

            if not raw_records:
                # Scraper jalan tapi tidak dapat data — catat sebagai failed
                logger.warning(f"[{label}] Scraper selesai tapi 0 records. Tandai sebagai GAGAL.")
                failed_states.append(label)
                continue

            logger.info(f"[{label}] {len(raw_records)} records didapat.")

            # ✅ Simpan langsung — data aman dari sini
            _save_state_batch(raw_records, state, list_type, run_dir)
            success_states.append(label)

        except Exception as exc:
            # Scraper crash — catat, lanjut ke state berikutnya
            logger.error(f"[{label}] Scraper CRASH: {exc}", exc_info=True)
            failed_states.append(label)
            # State lain tidak terpengaruh — loop lanjut

    # ── Stage 2: Summary scraping ──────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Scraping selesai. Berhasil: {len(success_states)} | Gagal: {len(failed_states)}")
    if success_states:
        logger.info(f"  ✅ Berhasil : {', '.join(success_states)}")
    if failed_states:
        logger.warning(f"  ❌ Gagal    : {', '.join(failed_states)}")
    logger.info("=" * 60)

    if not success_states:
        logger.error("Tidak ada state yang berhasil. Tidak ada file untuk di-merge.")
        return

    # ── Stage 3: Merge + normalize + export final ──────────────────────────────
    logger.info("[Merge] Memulai merge semua batch...")
    result = _merge_and_export(run_dir, args.skip_normalize, timestamp)

    if result is None:
        return

    df_out, final_csv, final_xlsx = result

    # ── Summary akhir ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Scraping selesai!")
    print(f"  Berhasil  : {len(success_states)}/{len(targets)} state")
    if failed_states:
        print(f"  Gagal     : {', '.join(failed_states)}")
    print(f"  Output dir: {run_dir}")
    print(f"  CSV final → {final_csv.name}")
    print(f"  XLSX      → {final_xlsx.name}")
    print(f"  Log       → {log_file}")
    if not args.skip_normalize:
        unmatched = df_out["anzsco_unit_group_code"].isna().sum()
        print(f"  Unmatched : {unmatched} records")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    args = parse_args()
    run(args)