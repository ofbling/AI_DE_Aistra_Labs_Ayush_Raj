-- side by side: the reconstruction above vs what's actually published
SELECT
    l.week_ending, l.channel,
    l.gross_sales_inr AS legacy_gross_sales_inr,
    r.reconstructed_gross_sales_inr,
    round(100.0 * (r.reconstructed_gross_sales_inr - l.gross_sales_inr)
          / NULLIF(l.gross_sales_inr, 0), 1) AS pct_diff,
    l.units_sold AS legacy_units_sold,
    r.reconstructed_units_sold
FROM read_csv_auto('data/reference/legacy_finance_weekly_report.csv') l
JOIN reconciliation.legacy_reconstruction r
    ON l.week_ending = r.week_ending::VARCHAR AND l.channel = r.channel
