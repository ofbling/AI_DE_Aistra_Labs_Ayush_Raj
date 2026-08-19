-- Marts dimension: dim_date
-- Direct load of the fiscal calendar reference. No defects, no
-- transformation -- Kestrel's fiscal year (April-March) is Finance-owned
-- and provided as-is; recomputing it independently would risk disagreeing
-- with the one calendar the business actually uses.

CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE TABLE marts.dim_date AS
SELECT
    calendar_date::DATE AS calendar_date,
    fiscal_year,
    fiscal_quarter,
    fiscal_month_no,
    iso_week,
    day_of_week,
    is_weekend::BOOLEAN AS is_weekend
FROM read_csv_auto('data/reference/fiscal_calendar.csv');
