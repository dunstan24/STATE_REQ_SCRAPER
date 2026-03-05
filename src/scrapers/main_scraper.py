"""
main.py — Run all state visa requirement scrapers

Urutan eksekusi:
  ACT → NT → NSW → QLD → SA → TAS → VIC → WA

Setiap state:
  1. Memanggil fungsi scrape utama → returns pd.DataFrame
  2. Memanggil export_results(df)  → saves per-state CSV / JSON / XLSX
  3. Jika gagal → skip, lanjut ke state berikutnya

Output:
  Per state : output_scrape/<state>/requirements_<state>.csv / .json / .xlsx
  Combined  : output_scrape/combined/requirements_all_states.csv / .json / .xlsx
  Log file  : main_scraper.log
"""

import importlib
import logging
import os
import sys
import time
import traceback

import pandas as pd

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("main_scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_COMBINED_DIR = os.path.join(_SCRIPT_DIR, "output_scrape", "combined")


# ── Safe import ───────────────────────────────────────────────────────────────

def _safe_import(module_name):
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        logger.error(f"[IMPORT] Gagal import '{module_name}': {e}")
        return None

act = _safe_import("act_req_scaper")
nt  = _safe_import("nt_req_scraper")
nsw = _safe_import("nsw_req_scraper")
qld = _safe_import("qld_req_scraper")
sa  = _safe_import("sa_req_scraper")
tas = _safe_import("tas_req_scraper")
vic = _safe_import("vic_req_scraper")
wa  = _safe_import("wa_req_scraper")


# ── Per-state runner ──────────────────────────────────────────────────────────

def run_state(state_name, scrape_fn, export_fn):
    """
    Jalankan satu state scraper dengan error handling.
    Return DataFrame jika sukses, None jika gagal.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"  Starting: {state_name}")
    logger.info(f"{'='*60}")
    start = time.time()

    try:
        df = scrape_fn()

        if df is None or df.empty:
            logger.warning(f"[{state_name}] DataFrame kosong — skip export.")
            return None

        export_fn(df)
        elapsed = time.time() - start
        logger.info(f"[{state_name}] Selesai dalam {elapsed:.1f}s — {len(df)} baris")
        return df

    except Exception:
        elapsed = time.time() - start
        logger.error(f"[{state_name}] GAGAL setelah {elapsed:.1f}s:\n{traceback.format_exc()}")
        return None


# ── ACT ───────────────────────────────────────────────────────────────────────

def scrape_act():
    df_190 = act.scrape_act_subclass(
        subclass=190,
        url_general="https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria",
        url_overseas="https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/overseas-applicant-eligibility",
        url_canberra="https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/canberra-resident-applicant-eligibility",
    )
    df_491 = act.scrape_act_subclass(
        subclass=491,
        url_general="https://www.act.gov.au/migration/skilled-migrants/491-nomination-criteria",
        url_overseas="https://www.act.gov.au/migration/skilled-migrants/491-nomination-criteria/491-nomination-overseas-applicant-eligibility",
        url_canberra="https://www.act.gov.au/migration/skilled-migrants/491-nomination-criteria/491-nomination-canberra-resident-applicant-eligibility",
    )
    return pd.concat([df_190, df_491], ignore_index=True)


# ── NSW ───────────────────────────────────────────────────────────────────────

def scrape_nsw():
    df_190 = nsw.scrape_nsw_subclass(
        subclass=190,
        url="https://www.nsw.gov.au/visas-and-migration/skilled-visas/skilled-nominated-visa-subclass-190",
        kw_general="Basic Eligibility",
        kw_details=[
            "Key Steps for Securing NSW Nomination",
            "Understanding Invitation Rounds and the NSW Skills List",
        ],
    )
    df_491 = nsw.scrape_nsw_subclass(
        subclass=491,
        url="https://www.nsw.gov.au/visas-and-migration/skilled-visas/skilled-work-regional-visa-subclass-491",
        kw_general="About NSW Nomination",
        kw_details=[
            "Understanding Invitation Rounds and the NSW Regional Skills List",
            "Key Steps for Securing NSW Nomination",
        ],
    )
    return pd.concat([df_190, df_491], ignore_index=True)


# ── QLD ───────────────────────────────────────────────────────────────────────

def scrape_qld():
    df_onshore  = qld.scrape_qld_pathway("Workers_Living_in_Queensland",
        "https://migration.qld.gov.au/visa-options/skilled-visas/skilled-workers-living-in-queensland")
    df_offshore = qld.scrape_qld_pathway("Workers_Living_Offshore",
        "https://migration.qld.gov.au/visa-options/skilled-visas/skilled-workers-living-offshore")
    df_building = qld.scrape_qld_pathway("Building_and_Construction",
        "https://migration.qld.gov.au/visa-options/skilled-visas/building-and-construction-workers")
    df_uni      = qld.scrape_qld_pathway("University_Graduates",
        "https://www.migration.qld.gov.au/visa-options/skilled-visas/graduates-of-a-queensland-university",
        component_id="component_1540893")
    df_business = qld.scrape_qld_business(
        "https://migration.qld.gov.au/visa-options/skilled-visas/small-business-owners-operating-in-regional-queensland")
    return pd.concat([df_onshore, df_offshore, df_building, df_uni, df_business], ignore_index=True)


# ── SA ────────────────────────────────────────────────────────────────────────

def scrape_sa():
    df_employment = sa.scrape_sa_pathway("Skilled_Employment_in_South_Australia", sa.URL_SA_EMPLOYMENT)
    df_graduates  = sa.scrape_sa_pathway("South_Australian_Graduates",            sa.URL_SA_GRADUATES)
    df_outer      = sa.scrape_sa_pathway("Outer_Regional_Skilled_Employment",     sa.URL_SA_OUTER)
    df_offshore   = sa.scrape_sa_offshore(sa.URL_SA_OFFSHORE)
    return pd.concat([df_employment, df_graduates, df_outer, df_offshore], ignore_index=True)


# ── TAS ───────────────────────────────────────────────────────────────────────

def scrape_tas():
    all_data = tas.scrape_all_pathways(tas.PATHWAY_URLS)
    return tas.build_wide_dataframe(all_data)


# ── Combined export ───────────────────────────────────────────────────────────

def export_combined(results, state_names):
    valid = [df for df in results if df is not None and not df.empty]
    if not valid:
        logger.error("[Combined] Tidak ada data untuk digabungkan.")
        return

    combined = pd.concat(valid, ignore_index=True)
    os.makedirs(_COMBINED_DIR, exist_ok=True)

    csv_path  = os.path.join(_COMBINED_DIR, "requirements_all_states.csv")
    json_path = os.path.join(_COMBINED_DIR, "requirements_all_states.json")
    xlsx_path = os.path.join(_COMBINED_DIR, "requirements_all_states.xlsx")

    combined.to_csv(csv_path,   index=False, encoding="utf-8-sig")
    combined.to_json(json_path, orient="records", indent=4)

    try:
        combined.to_excel(xlsx_path, index=False, engine="openpyxl")
        try:
            from general_tools_scrap import format_excel
            format_excel(xlsx_path)
        except Exception:
            pass
        logger.info(f"[Combined] XLSX → {xlsx_path}")
    except Exception as e:
        logger.warning(f"[Combined] Gagal export XLSX: {e}")

    logger.info(f"[Combined] {len(combined)} total baris dari {len(valid)} state")

    print(f"\n{'='*60}")
    print(f"  COMBINED: {len(combined)} rows dari {len(valid)}/8 states")
    print(f"  -> {csv_path}")
    print(f"{'='*60}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    total_start  = time.time()
    state_names  = ["ACT", "NT", "NSW", "QLD", "SA", "TAS", "VIC", "WA"]
    results      = []

    logger.info("=" * 60)
    logger.info("  MULAI: All State Visa Requirements Scraper")
    logger.info("=" * 60)

    # ── ACT ──────────────────────────────────────────────────────────────
    if act:
        results.append(run_state("ACT", scrape_act, act.export_results))
    else:
        logger.warning("[ACT] Skipped — module tidak tersedia.")
        results.append(None)

    # ── NT ───────────────────────────────────────────────────────────────
    if nt:
        results.append(run_state("NT", nt.scrape_nt, nt.export_results))
    else:
        logger.warning("[NT] Skipped — module tidak tersedia.")
        results.append(None)

    # ── NSW ──────────────────────────────────────────────────────────────
    if nsw:
        results.append(run_state("NSW", scrape_nsw, nsw.export_results))
    else:
        logger.warning("[NSW] Skipped — module tidak tersedia.")
        results.append(None)

    # ── QLD ──────────────────────────────────────────────────────────────
    if qld:
        results.append(run_state("QLD", scrape_qld, qld.export_results))
    else:
        logger.warning("[QLD] Skipped — module tidak tersedia.")
        results.append(None)

    # ── SA ───────────────────────────────────────────────────────────────
    if sa:
        results.append(run_state("SA", scrape_sa, sa.export_results))
    else:
        logger.warning("[SA] Skipped — module tidak tersedia.")
        results.append(None)

    # ── TAS ──────────────────────────────────────────────────────────────
    if tas:
        results.append(run_state("TAS", scrape_tas, tas.export_results))
    else:
        logger.warning("[TAS] Skipped — module tidak tersedia.")
        results.append(None)

    # ── VIC ──────────────────────────────────────────────────────────────
    if vic:
        results.append(run_state("VIC", vic.scrape_vic, vic.export_results))
    else:
        logger.warning("[VIC] Skipped — module tidak tersedia.")
        results.append(None)

    # ── WA ───────────────────────────────────────────────────────────────
    if wa:
        results.append(run_state("WA", wa.scrape_wa, wa.export_results))
    else:
        logger.warning("[WA] Skipped — module tidak tersedia.")
        results.append(None)

    # ── Combined output ───────────────────────────────────────────────────
    export_combined(results, state_names)

    # ── Summary ───────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    successful    = sum(1 for r in results if r is not None)

    logger.info(f"\n{'='*60}")
    logger.info(f"  SELESAI — {successful}/8 states OK")
    logger.info(f"  Total waktu: {total_elapsed:.1f}s ({total_elapsed/60:.1f} menit)")
    logger.info("  Status per state:")
    for name, result in zip(state_names, results):
        if result is not None:
            logger.info(f"    {name:5s} : OK ({len(result)} baris)")
        else:
            logger.info(f"    {name:5s} : GAGAL")
    logger.info(f"{'='*60}")

    print(f"\nSelesai! {successful}/8 states berhasil dalam {total_elapsed/60:.1f} menit.")
    print("Lihat main_scraper.log untuk detail lengkap.")