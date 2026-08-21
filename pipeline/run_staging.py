from pathlib import Path
import duckdb

DB_PATH = "warehouse.duckdb"
DATA = Path("data") / "raw"
BAD_REEFER_FILE = DATA / "reefer_telemetry" / "dt=2025-07-14" / "part-00000.parquet"
SQL_FILES = [
    "sql/staging/stg_pos_transactions.sql",
    "sql/staging/stg_reefer_telemetry.sql",
    "sql/staging/stg_wms_scan_events.sql",
]

def reefer_file_list_literal():
    paths = sorted((DATA / "reefer_telemetry").glob("*/*.parquet"))
    paths = [p for p in paths if p != BAD_REEFER_FILE]
    return "[" + ", ".join(f"'{p.as_posix()}'" for p in paths) + "]"

def main():
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS staging")
    for path in SQL_FILES:
        sql = Path(path).read_text(encoding="utf-8").replace("{{REEFER_FILES}}", reefer_file_list_literal())
        con.execute(sql)
    n_pos = con.sql("SELECT count(*) FROM staging.pos_transactions").fetchone()[0]
    raw_pos = con.sql("SELECT count(*) FROM read_parquet('data/raw/pos_transactions/*/*.parquet', union_by_name=true)").fetchone()[0]
    print(f"pos_transactions: {n_pos:,} ({raw_pos - n_pos:,} dupes dropped)")
    n_tel = con.sql("SELECT count(*) FROM staging.reefer_telemetry").fetchone()[0]
    print(f"reefer_telemetry: {n_tel:,}")
    n_wms = con.sql("SELECT count(*) FROM staging.wms_scan_events").fetchone()[0]
    print(f"wms_scan_events: {n_wms:,}")

if __name__ == "__main__":
    main()