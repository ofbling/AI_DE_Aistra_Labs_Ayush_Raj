"""
feed completeness report -- answers illustrative question 8: which days are
missing data, in any feed, and how would we know without being told.

checks three different things, because no single check covers everything:
1. per-partition row counts vs the manifest (catches broken/truncated files)
2. gateway-level day gaps in reefer_telemetry (catches silent outages,
   without hardcoding which gateway or which dates -- general anomaly check)
3. partition presence for erp_cdc feeds, which have no manifest at all

run after generating the dataset:
    python scripts/feed_completeness_report.py
"""
from pathlib import Path
import duckdb

DATA_DIR = Path("data")
RAW = DATA_DIR / "raw"

MANIFESTED_FEEDS = {
    "pos_transactions": "ingest_date",
    "reefer_telemetry": "dt",
    "wms_scan_events": "dt",
}
UNMANIFESTED_FEEDS = ["erp_cdc/outlet_master", "erp_cdc/product_master", "erp_cdc/sales_order_header"]


def per_partition_reconciliation(con):
    print("=== 1. per-partition row counts vs manifest ===")
    manifest = con.sql(f"""
        SELECT feed, partition, row_count
        FROM read_csv_auto('{DATA_DIR.as_posix()}/_manifest/expected_partitions.csv')
    """).df()

    for feed, part_col in MANIFESTED_FEEDS.items():
        feed_dir = RAW / feed
        partitions = sorted(p for p in feed_dir.glob(f"{part_col}=*") if p.is_dir())
        mismatches = []
        for part_dir in partitions:
            expected_row = manifest[(manifest.feed == feed) & (manifest.partition == part_dir.name)]
            expected = int(expected_row.row_count.iloc[0]) if len(expected_row) else None
            try:
                # own connection here -- a bad partition shouldn't poison
                # the shared one the checks after this one still need
                with duckdb.connect() as probe:
                    actual = probe.sql(
                        f"SELECT count(*) FROM read_parquet('{part_dir.as_posix()}/*.parquet', union_by_name=true)"
                    ).fetchone()[0]
            except Exception as e:
                mismatches.append((part_dir.name, expected, "UNREADABLE", str(e)[:80]))
                continue
            if expected is not None and actual != expected:
                mismatches.append((part_dir.name, expected, actual, ""))

        if mismatches:
            print(f"\n{feed}: {len(mismatches)} partition(s) don't match the manifest")
            for name, expected, actual, note in mismatches:
                print(f"  {name}: manifest={expected} actual={actual} {note}")
        else:
            print(f"{feed}: all {len(partitions)} partitions match the manifest")


def gateway_gap_check(con):
    print("\n=== 2. reefer_telemetry gateway-level day gaps ===")
    # excludes the known-unreadable file so this can actually run --
    # that one's already caught by check 1
    bad_file = RAW / "reefer_telemetry" / "dt=2025-07-14" / "part-00000.parquet"
    files = [p.as_posix() for p in sorted((RAW / "reefer_telemetry").glob("*/*.parquet")) if p != bad_file]
    file_list = "[" + ", ".join(f"'{p}'" for p in files) + "]"

    gaps = con.sql(f"""
        WITH daily AS (
            SELECT gateway_id, dt, count(*) AS readings
            FROM read_parquet({file_list}, hive_partitioning=true)
            GROUP BY gateway_id, dt
        ),
        gateway_range AS (
            SELECT gateway_id, min(dt) AS first_seen, max(dt) AS last_seen
            FROM daily GROUP BY gateway_id
        ),
        all_days AS (SELECT DISTINCT dt FROM daily),
        expected AS (
            SELECT g.gateway_id, d.dt
            FROM gateway_range g
            JOIN all_days d ON d.dt BETWEEN g.first_seen AND g.last_seen
        )
        SELECT e.gateway_id, e.dt
        FROM expected e
        LEFT JOIN daily d ON e.gateway_id = d.gateway_id AND e.dt = d.dt
        WHERE d.readings IS NULL
        ORDER BY e.gateway_id, e.dt
    """).df()

    if len(gaps):
        print(f"{len(gaps)} gateway-day gap(s) found, not flagged anywhere else:")
        print(gaps.to_string(index=False))
    else:
        print("no gaps found")


def unmanifested_feed_presence(con):
    print("\n=== 3. erp_cdc partition presence (no manifest exists for these) ===")
    for feed in UNMANIFESTED_FEEDS:
        feed_dir = RAW / feed
        partitions = sorted(p.name for p in feed_dir.glob("extract_date=*") if p.is_dir())
        print(f"{feed}: {len(partitions)} extract_date partitions, "
              f"{partitions[0]} to {partitions[-1]}")
    print(
        "\nnote: expected_partitions.csv only covers pos_transactions, "
        "reefer_telemetry, and wms_scan_events -- nothing checks erp_cdc "
        "completeness at all today, beyond this script existing."
    )


def main():
    con = duckdb.connect()
    per_partition_reconciliation(con)
    gateway_gap_check(con)
    unmanifested_feed_presence(con)


if __name__ == "__main__":
    main()
