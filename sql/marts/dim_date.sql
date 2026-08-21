-- just loading finance's own fiscal calendar, not recalculating it --
-- don't want to risk disagreeing with the one calendar the business uses

CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE TABLE marts.dim_date AS
SELECT calendar_date::DATE AS calendar_date, fiscal_year, fiscal_quarter,
    fiscal_month_no, iso_week, day_of_week, is_weekend::BOOLEAN AS is_weekend
FROM read_csv_auto('data/reference/fiscal_calendar.csv');