"""
Phase 1 — raw feed validation.

Confirms the shipped dataset matches _manifest/expected_partitions.csv, and
empirically checks a handful of the defects documented in generate_dataset.py
before any pipeline logic gets built on assumptions about them.

Run after generating the dataset:
    python3 generate_dataset.py --scale 1 --out data
    python3 scripts/validate_raw.py
"""
import sys
from pathlib import Path

import duckdb

DATA_DIR = Path("data")
RAW = DATA_DIR / "raw"


def main() -> None:
    if not RAW.exists():
        sys.exit(
            "data/raw not found. Generate it first:\n"
            "  python3 generate_dataset.py --scale 1 --out data"
        )

    con = duckdb.connect()

    feed_globs = {
        "pos_transactions": f"{RAW}/pos_transactions/*/*.parquet",
        "reefer_telemetry": f"{RAW}/reefer_telemetry/*/*.parquet",
        "wms_scan_events": f"{RAW}/wms_scan_events/*/*.parquet",
    }

    print("\n=== 1. Row counts vs manifest ===")
    manifest = con.sql(f"""
        SELECT feed, SUM(row_count) AS expected_rows
        FROM read_csv_auto('{DATA_DIR}/_manifest/expected_partitions.csv')
        GROUP BY feed
    """).df()

    for feed, glob in feed_globs.items():
        expected = int(manifest.loc[manifest.feed == feed, "expected_rows"].iloc[0])
        try:
            actual = con.sql(
                f"SELECT count(*) FROM read_parquet('{glob}', union_by_name=true)"
            ).fetchone()[0]
        except Exception as e:
            print(f"[FAIL] {feed}: could not read all partitions -> {e}")
            continue
        diff = actual - expected
        tag = "OK" if diff == 0 else "FAIL"
        print(f"[{tag}] {feed}: manifest {expected:,} | actual {actual:,} | diff {diff:+,}")

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

    print("\n=== 4. Gateway GW-017 outage (DEFECT L10) ===")
    outage = con.sql(f"""
        SELECT dt, count(*) AS readings
        FROM read_parquet('{feed_globs["reefer_telemetry"]}', hive_partitioning=true)
        WHERE gateway_id = 'GW-017' AND dt BETWEEN '2026-02-09' AND '2026-02-14'
        GROUP BY dt ORDER BY dt
    """).df()
    print(outage.to_string(index=False))

    print("\n=== 5. temp_unit nulls by vendor (DEFECT L7) ===")
    nulls = con.sql(f"""
        SELECT telemetry_vendor, count(*) AS readings,
               count(*) FILTER (WHERE temp_unit IS NULL) AS null_unit,
               round(100.0 * count(*) FILTER (WHERE temp_unit IS NULL) / count(*), 1) AS pct_null
        FROM read_parquet('{feed_globs["reefer_telemetry"]}')
        GROUP BY telemetry_vendor
    """).df()
    print(nulls.to_string(index=False))

    print("\n=== 6. uom_conversion coverage vs product_master (DEFECT L16) ===")
    coverage = con.sql(f"""
        WITH skus AS (
            SELECT DISTINCT sku_code
            FROM read_parquet('{RAW}/erp_cdc/product_master/*/*.parquet')
        )
        SELECT
            (SELECT count(*) FROM skus) AS distinct_skus,
            (SELECT count(*) FROM read_csv_auto('{DATA_DIR}/reference/uom_conversion.csv')) AS uom_rows,
            (SELECT count(*) FROM skus s
             WHERE NOT EXISTS (
                 SELECT 1 FROM read_csv_auto('{DATA_DIR}/reference/uom_conversion.csv') u
                 WHERE u.sku_code = s.sku_code
             )) AS skus_missing_conversion
    """).df()
    print(coverage.to_string(index=False))

    print("\nDone — these numbers are your DECISIONS.md evidence, not assumptions.")


if __name__ == "__main__":
    main()
