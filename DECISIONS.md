# Decisions

## Scope

Built: raw validation → staging → clean (CDC/SCD2 replay) → marts → KPI
catalogue, a reconciliation of the legacy Finance report against the raw
feeds, and a local natural-language query layer over the marts.

Not built, and why:
- Any breakdown "by carrier" -- no carrier_id exists in any raw feed.
  `dim_carrier` loads fine but is unlinkable to anything else.
- Per-item warehouse cycle time -- `wms_scan_events` has no key tying a
  RECEIVE scan to its matching DISPATCH scan (warehouse/order/sku/batch/
  pallet are independently randomized per scan in the source data). The
  KPI catalogue's cycle-time metric is a warehouse-level proxy, not a
  per-order measurement, and says so explicitly.

## Local LLM instead of a hosted API

The ask-anything layer was built against the Anthropic API first, then
switched to Ollama (`qwen2.5-coder:7b`, fully local) after hitting
billing limits on a personal account. The trade-off was tested directly,
not assumed, and pushed through two separate kinds of hardening before
being accepted as a real limitation rather than a bug:

**Mechanical reliability (fully solved)**: bounded the tool-call loop so
it can't hang on an unbounded retry; recovered tool calls that some
models print as plain JSON text instead of using the real
function-calling API; added an order-independent result comparison so
the loop stops as soon as two rounds agree instead of always burning
every retry even when round one was already correct.

**Reasoning reliability (a real, remaining ceiling)**: once the
mechanics were solid, schema-grounding accuracy split cleanly in two --
- Reliable on direct single-table lookups (e.g. "orders by source
  system") -- correct schema, first try, every time tested.
- Not reliable on multi-table / time-windowed questions (e.g. "gross
  sales by channel for the last complete fiscal quarter") -- picks the
  wrong table, then compounds it by chasing DuckDB's fuzzy-match error
  suggestions into unrelated columns, or inventing placeholder literals
  like `'your_order_id_here'`. Reproduced near-identically on two
  different model families (`llama3.1:8b` and `qwen2.5-coder:7b`) after
  multiple rounds of prompt hardening and with the mechanics fully
  fixed -- a genuine capability ceiling of 7-8B local models on this
  task, not a prompt-wording or code problem.

The mitigation is architectural, not a prompt fix: every query the
model runs is printed before its result, so a wrong answer is visible
and auditable in the same terminal, never trusted silently -- the
actual answer to "if it cannot show me the query it ran, I am not
interested." At real scale I'd either use a hosted frontier model or
narrow the interface to parameterized templates instead of free-form
SQL generation for anything past single-table lookups.

## Findings worth flagging (not bugs -- the data's own gaps)

- **Cold Chain Integrity**: naive excursion rate 38.29% vs. 7.19%
  normalized. Entirely a Fahrenheit/Celsius unit bug on COLDEYE sensors
  (100% naive vs 7.2% normalized once corrected) -- matches the CFO
  brief's "~1/3" intuition to the undiscovered-bug number, not the true
  rate.
- **Service Level**: 0.0% for every channel and warehouse. `DELIVERED`
  is structurally unreachable in the source data's status field.
  Documented as-is rather than redefined against DISPATCHED -- the
  metric answers exactly what the brief defines, and the 0% is the
  finding.
- **Warehouse Cycle Time proxy**: 71-81 minutes across the 8 warehouses,
  matching the source data's fixed ~75-minute stage-offset mechanic --
  flagged so it isn't read as a genuine ops insight.
- **Legacy Finance report**: reconstructed and compared against the raw
  feeds directly -- correlation ≈ 0.005. The legacy numbers aren't
  derived from this data at all (full detail in RECONCILIATION.md).

## Two real pipeline bugs found and fixed

- `fact_sales.sql` joined dimension validity windows against the
  IST-shifted timestamp against un-shifted CDC valid_from/valid_to --
  fixed to UTC on both sides.
- `orders_current.sql`'s "latest row wins" logic ordered by
  `op_ts DESC`, which let deletes lose to later real updates because
  delete rows keep the original insert's stale op_ts -- fixed to order
  by `seq DESC`, which delete rows always win on regardless of
  timestamp.

## Git history

Kept the real commit history intact, including the mid-project bug
fixes and the failed rollback attempt -- deleting it and rebuilding a
"clean" version would have hidden exactly the debugging process this
kind of role actually involves. The Precision Log has the full
chronological detail; this file is the summary.

## Scale / production notes

- Single-file DuckDB is fine at this volume; a real multi-user
  production setting would need a proper warehouse (Snowflake/BigQuery/
  Databricks) instead.
- Every layer rebuilds fully via `CREATE OR REPLACE TABLE` on each run --
  simple and idempotent for a project this size, but wouldn't scale;
  production needs real incremental/merge logic, not full rebuilds.
- Not tested at the generator's `--scale 10` multiplier. The design
  (idempotent rebuilds, disposable-connection pattern around risky
  reads) should hold, but this wasn't empirically verified, so it isn't
  claimed as proven.
