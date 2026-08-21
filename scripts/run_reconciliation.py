"""
legacy finance report reconciliation -- builds the reconstruction
(reproducing the two documented bugs) and compares it to what's published.

    python scripts/run_reconciliation.py
"""
import duckdb

con = duckdb.connect("warehouse.duckdb")
con.execute("CREATE SCHEMA IF NOT EXISTS reconciliation")
con.execute(open("sql/reconciliation/legacy_report_reconstruction.sql").read())

comparison_sql = open("sql/reconciliation/legacy_report_comparison.sql").read().rstrip().rstrip(";")
con.execute(f"CREATE OR REPLACE TABLE reconciliation.comparison AS {comparison_sql}")

print(con.sql("SELECT * FROM reconciliation.comparison ORDER BY week_ending, channel").df().to_string(index=False))

summary = con.sql("""
    SELECT
        count(*) AS weeks_compared,
        round(avg(abs(pct_diff)), 1) AS avg_abs_pct_diff,
        round(min(pct_diff), 1) AS min_pct_diff,
        round(max(pct_diff), 1) AS max_pct_diff,
        round(corr(legacy_gross_sales_inr, reconstructed_gross_sales_inr), 3) AS correlation
    FROM reconciliation.comparison
""").df()
print("\nsummary:")
print(summary.to_string(index=False))
