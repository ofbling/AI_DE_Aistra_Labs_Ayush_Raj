-- loaded for completeness but nothing joins to this -- no feed carries a
-- carrier_id or route->carrier mapping anywhere, kills the "by carrier" ask

CREATE OR REPLACE TABLE marts.dim_carrier AS
SELECT carrier_id, carrier_name, mode, sla_hours, rate_per_km
FROM read_csv_auto('data/reference/carrier_master.csv');