"""
sanity check: discount_amount should divide cleanly by (unit_price * qty)
back to 5% or 10% -- confirms qty is the right basis for revenue, not
qty_eaches. run after run_marts.py.
"""
import duckdb

con = duckdb.connect("warehouse.duckdb")
result = con.sql("""
    SELECT round(discount_amount / NULLIF(unit_price * qty, 0), 3) AS rate, count(*) AS lines
    FROM marts.fact_sales
    WHERE discount_amount > 0
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
""").df()
print(result.to_string(index=False))
