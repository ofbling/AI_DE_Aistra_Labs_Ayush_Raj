"""
One-time check: confirm that unit_price * qty (not qty_eaches) is the
correct basis for revenue figures, by checking that discount_amount
divides cleanly back out to the generator's known discount rates (0%, 5%,
10%) when divided by (unit_price * qty).

Run:
    python scripts/verify_gross_sales_formula.py
"""
import duckdb

con = duckdb.connect("warehouse.duckdb")

result = con.sql("""
    SELECT
        round(discount_amount / NULLIF(unit_price * qty, 0), 3) AS implied_discount_rate,
        count(*) AS lines
    FROM marts.fact_sales
    WHERE discount_amount > 0
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 10
""").df()

print("Implied discount rate = discount_amount / (unit_price * qty):")
print(result.to_string(index=False))
print(
    "\nIf this clusters tightly at 0.05 and 0.10, that confirms raw qty "
    "(not qty_eaches) is what discount_amount was actually computed "
    "against in the source data -- so gross sales must use qty too, or "
    "the two won't reconcile."
)
