# Kestrel Provisions — Analytical Foundation and Metric Layer

A DuckDB-based warehouse built from Kestrel's raw feeds: staging →
clean (CDC/SCD2 replay) → marts → a KPI catalogue, plus a legacy report
reconciliation and a local natural-language query layer.

**Start with [DECISIONS.md](DECISIONS.md)** — one page, the judgment
calls and trade-offs, meant to be read before any of the code below.

## Prerequisites

- Python 3.x (on Windows, use `python`, not `python3` — see Gotchas)
- [Ollama](https://ollama.com) — only needed for the ask-anything layer
  (`ask/ask_anything.py`); everything else runs without it

## Setup

```
git clone https://github.com/ofbling/AI_DE_Aistra_Labs_Ayush_Raj.git
cd AI_DE_Aistra_Labs_Ayush_Raj

python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt

ollama pull qwen2.5-coder:7b      # only if you want ask-anything
```

`data/` and `warehouse.duckdb` are gitignored — nothing under them ships
in the repo. The steps below regenerate everything locally.

## Running the pipeline

Run these in order from the repo root. Each one prints row counts and
integrity checks as it goes — that output is how you confirm it worked,
there's no separate test suite.

```
python generate_dataset.py              # produces data/raw, data/reference, data/_manifest
python scripts/validate_raw.py          # sanity check against the manifest (reefer_telemetry L18 is *expected* to fail)
python pipeline/run_staging.py          # staging.*
python pipeline/run_clean.py            # clean.*  (CDC/SCD2 replay)
python pipeline/run_marts.py            # marts.*  (facts + dims, referential checks)
```

All four pipeline scripts are `CREATE OR REPLACE TABLE` end to end —
safe to re-run any of them any number of times against the same
`warehouse.duckdb`.

The generator also supports a `--scale` multiplier for a larger smoke
test (`python generate_dataset.py --scale 10`); this build wasn't
exercised at that scale — see DECISIONS.md.

## Repo structure

```
sql/staging/      mechanical fixes only -- schema drift, timezone, dedup
sql/clean/        CDC point-in-time replay (SCD2 dims, latest-wins facts)
sql/marts/        joined facts + dims, ready to query
sql/kpis/         parameterized queries ($start_date/$end_date) backing KPI_CATALOGUE.md
sql/reconciliation/  legacy Finance report reconstruction + comparison

pipeline/         one runner script per layer (staging, clean, marts)
scripts/          standalone checks -- not part of the sequential pipeline:
  validate_raw.py               raw feeds vs. the manifest
  verify_gross_sales_formula.py confirms qty (not qty_eaches) is the revenue basis
  feed_completeness_report.py   per-partition + gateway-gap + CDC presence checks
  data_quality_investigations.py  outlet/product join-gap breakdown, cold chain naive-vs-normalized, WMS linkage check
  run_reconciliation.py         rebuilds the legacy report bugs against real data

kpi_catalogue/KPI_CATALOGUE.md  9 KPI definitions with real confirmed numbers
ask/ask_anything.py             local NL-to-SQL layer over marts/clean, via Ollama

DECISIONS.md        read first
RECONCILIATION.md   the legacy Finance report finding
README.md           this file
```

## Querying the data

**KPIs**: each file in `sql/kpis/` is a parameterized query (`$start_date`,
`$end_date`) — read the file for the exact definition and bind a real
date range via the DuckDB Python API against `warehouse.duckdb`, or ask
for it in plain English instead (see below).

**Ask anything**:
```
python ask/ask_anything.py
> gross sales by channel last month
```
Runs fully local via Ollama — no API key, nothing leaves the machine.
Every SQL query it runs is printed before the result, so an answer is
always auditable, never silently trusted. It's reliable on direct
single-table lookups and inconsistent on multi-table/time-windowed
questions — see DECISIONS.md for what was tested and why that's a
model limitation, not a bug.

## Gotchas

- This machine only has `python` registered, not `python3` — use
  `python` for every command above.
- `ollama pull` / `ollama serve` are independent of the Python venv —
  run them in any terminal, venv active or not.
- `reefer_telemetry` failing validation on `dt=2025-07-14` is expected
  (a deliberately truncated file, DEFECT L18) — `run_staging.py` excludes
  it explicitly rather than letting it fail the whole read.
