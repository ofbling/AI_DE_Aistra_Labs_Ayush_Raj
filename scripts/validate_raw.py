"""
Phase 1 — raw feed validation.

Confirms the shipped dataset matches _manifest/expected_partitions.csv, and
empirically checks a handful of the defects documented in generate_dataset.py
before any pipeline logic gets built on assumptions about them.

Run after generating the dataset:
    python generate_dataset.py --scale 1 --out data
    python scripts/validate_raw.py
"""
import sys
from pathlib import Path

import duckdb

DATA_DIR = Path("data")
RAW = DATA_DIR / "raw"

# DEFECT L18: this file is deliberately truncated by the generator but still
# counted in the manifest. Excluded explicitly wherever a section needs a
# full, readable scan of reefer_telemetry.
BAD_REEFER_FILE = RAW / "reefer_telemetry" / "dt=2025-07-14" / "part-00000.parquet"


def reefer_files(exclude=None):
    """All reefer_telemetry parquet files as posix-style paths, optionally
    excluding one. Forward slashes only, so paths embed into SQL cleanly on
    Windows without backslash-escaping surprises."""
    paths = sorted((RAW / "reefer_telemetry").glob("*/*.parquet"))
    if exclude is not None:
        paths = [p for p in paths if p != exclude]
    return [p.as_posix() for p in paths]


def parquet_list_literal(paths):
    """Turn a list of file paths into a DuckDB SQL list literal: ['a','b']."""
    return "[" + ", ".join(f"'{p}'" for p in paths) + "]"


def main() -> None:
    if not RAW.exists():
        sys.exit(
            "data/raw not found. Generate it first:\n"
            "  python generate_dataset.py --scale 1 --out data"
        )

    con = duckdb.connect()

    feed_globs = {
        "pos_transactions": f"{RAW.as_posix()}/pos_transactions/*/*.parquet",
        "reefer_telemetry": f"{RAW.as_posix()}/reefer_telemetry/*/*.parquet",
        "wms_scan_events": f"{RAW.as_posix()}/wms_scan_events/*/*.parquet",
    }

    print("\n=== 1. Row counts vs manifest ===")
    manifest = con.sql(f"""
        SELECT feed, SUM(row_count) AS expected_rows
        FROM read_csv_auto('{DATA_DIR.as_posix()}/_manifest/expected_partitions.csv')
        GROUP BY feed
    """).df()

    for feed, glob in feed_globs.items():
        expected = int(manifest.loc[manifest.feed == feed, "expected_rows"].iloc[0])
        try:
            actual = con.sql(
                f"SELECT count(*) FROM read_parquet('{glob}', union_by_name=true)"
            ).fetchone()[0]
        except Exception as e:
            con.rollback()
            print(f"[FAIL] {feed}: could not read all partitions -> {e}")
            continue
        diff = actual - expected
        tag = "OK" if diff == 0 else "FAIL"
        print(f"[{tag}] {feed}: manifest {expected:,} | actual {actual:,} | diff {diff:+,}")

    print(
        "\n  ^ reefer_telemetry failing above is expected: DEFECT L18 truncates "
        f"{BAD_REEFER_FILE.name} in the {BAD_REEFER_FILE.parent.name} partition "
        "after the manifest was already written. The manifest still claims the "
        "original row count; the file itself is unreadable. This is exactly the "
        "kind of gap illustrative question 8 asks about — trusting the manifest "
        "alone would have hidden it completely."
    )

    print("\n=== 2. pos_transactions schema drift (DEFECT L4) ===")
    drift = con.sql(f"""
        SELECT ingest_date < '2025-10-01' AS pre_drift, count(*) AS rows
        FROM read_parquet('{feed_globs["pos_transactions"]}',
                           hive_partitioning=true, union_by_name=true)
        GROUP BY 1
    """).df()
    print(drift.to_string(index=False))

    print("\n=== 3. Exact duplicate rows in pos_transactions (DEFECT L3) ===")
    dupe = con.sql(f"""
        SELECT count(*) AS total_rows,
               count(*) FILTER (WHERE rn > 1) AS duplicate_rows
        FROM (
            SELECT *, row_number() OVER (
                PARTITION BY txn_id, txn_line_no ORDER BY txn_id
            ) AS rn
            FROM read_parquet('{feed_globs["pos_transactions"]}', union_by_name=true)
        )
    """).df()
    total, dupes = int(dupe.total_rows[0]), int(dupe.duplicate_rows[0])
    print(f"  total rows: {total:,}   duplicates: {dupes:,} ({dupes/total:.2%})")

    # Sections 4 and 5 need every reefer_telemetry file EXCEPT the truncated
    # one — a partial WHERE filter can't save a read that fails at the file
    # level, so the bad file has to be excluded from the scan itself.
    clean_files = parquet_list_literal(reefer_files(exclude=BAD_REEFER_FILE))

    print("\n=== 4. Gateway GW-017 outage (DEFECT L10) ===")
    outage = con.sql(f"""
        SELECT dt, count(*) AS readings
        FROM read_parquet({clean_files}, hive_partitioning=true)
        WHERE gateway_id = 'GW-017' AND dt BETWEEN '2026-02-09' AND '2026-02-14'
        GROUP BY dt ORDER BY dt
    """).df()
    print(outage.to_string(index=False))

    print("\n=== 5. temp_unit nulls by vendor (DEFECT L7) ===")
    nulls = con.sql(f"""
        SELECT telemetry_vendor, count(*) AS readings,
               count(*) FILTER (WHERE temp_unit IS NULL) AS null_unit,
               round(100.0 * count(*) FILTER (WHERE temp_unit IS NULL) / count(*), 1) AS pct_null
        FROM read_parquet({clean_files})
        GROUP BY telemetry_vendor
    """).df()
    print(nulls.to_string(index=False))

    print("\n=== 6. uom_conversion coverage vs product_master (DEFECT L16) ===")
    coverage = con.sql(f"""
        WITH skus AS (
            SELECT DISTINCT sku_code
            FROM read_parquet('{RAW.as_posix()}/erp_cdc/product_master/*/*.parquet')
        )
        SELECT
            (SELECT count(*) FROM skus) AS distinct_skus,
            (SELECT count(*) FROM read_csv_auto('{DATA_DIR.as_posix()}/reference/uom_conversion.csv')) AS uom_rows,
            (SELECT count(*) FROM skus s
             WHERE NOT EXISTS (
                 SELECT 1 FROM read_csv_auto('{DATA_DIR.as_posix()}/reference/uom_conversion.csv') u
                 WHERE u.sku_code = s.sku_code
             )) AS skus_missing_conversion
    """).df()
    print(coverage.to_string(index=False))

    print("\nDone — these numbers are your DECISIONS.md evidence, not assumptions.")


if __name__ == "__main__":
    main()
