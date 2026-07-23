# Data Ingestion Architecture in RetailOS

## Overview

RetailOS ingests data via batch CSV processing, a scheduler that automates
that batch process, and a near-real-time WebSocket order stream. A prior
version of this document called the system "production-ready" and
"designed to run 24/7" - it can run continuously, but several pieces are
narrower than that framing suggested (schema-drift detection only covers
one table; the "adaptive schema manager" isn't wired into what actually
gets ingested). Corrected below.

---

## 1. Batch Ingestion Pipeline

**File:** `src/ingestion/batch_pipeline.py`

### What it does
Reads each CSV in `data/raw/`, validates against a schema registry,
quarantines invalid rows, writes valid rows to timestamped Parquet.

### Key features
- ✅ Auto-retry on read failures (exponential backoff, real -
  `_read_with_retries`)
- ✅ Quarantine system for invalid records, with a `quarantine_reason` column
- ⚠️ Schema validation - real, but `default_schema_registry()` currently
  registers every table with `required_columns=[]`, so in practice no rows
  ever get quarantined for missing/invalid required fields. The mechanism
  works; it's just not configured with any actual required columns today.
- ✅ Schema drift *logging* (new/unexpected columns are logged, not
  rejected) - this part of `_validate_and_split` works regardless of the
  empty required-columns list.

### Data flow
```
CSV Files (data/raw/)
    v
Read with retries
    v
Validate against schema (currently: no required columns configured)
    v
Split: Valid vs Invalid
    v
Valid -> Parquet (data/raw/{table}_{timestamp}.parquet)
Invalid -> Quarantine (data/quarantine/{table}_quarantine_{timestamp}.csv)
```

### Tables processed
Defined once in `batch_pipeline.TABLE_CSV_PAIRS` (used by both
`default_schema_registry()` and `run_all()`, so they can't drift apart):
`customers`, `products`, `stores`, `inventory`, `transactions`,
`shipments`, `web_clickstream`.

### Run manually
```bash
python -m src.ingestion.batch_pipeline
```

---

## 2. Automated Batch Scheduler

**File:** `src/ingestion/batch_scheduler.py`

### Scheduled jobs
| Job | Frequency | What it actually does |
|-----|-----------|------------------------|
| **Batch Ingestion** | Every 6 hours | `run_all(pipeline)` over all 7 tables, then `DataCleaner().run()` (transactions only), then `partition_fact_sales()` |
| **ML Retraining** | Daily at 2 AM | Constructs a fresh `MLPredictiveEngine()` (trains automatically in `__init__`) |
| **Data Quality Checks** | Every 30 minutes | Counts recent rows in `quarantine_log` if that table exists (best-effort, wrapped in try/except) |
| **Log Cleanup** | Weekly (Sunday 3 AM) | Deletes `pipeline_runs` older than 90 days |

### Pipeline stages (Stage 1 of `run_batch_ingestion`)
1. **Stage 1**: `run_all(pipeline)` - ingest all 7 tables (see above)
2. **Stage 2**: `DataCleaner().run()` - cleans `transactions.csv` only
   (dedup, null-fill, negative-price fix, future-date filter, anomaly
   flagging); writes `docs/DATA_QUALITY.md` as evidence
3. **Stage 3**: `partition_fact_sales()` - writes a partitioned Parquet
   copy of `fact_sales` (see `docs/STORAGE.md` for real benchmark numbers
   - it's measurably *slower* than the native DuckDB table at this data
   volume, not faster)

**Note:** none of these three stages loads data into the DuckDB warehouse
tables (`dim_*`/`fact_*`) - that only happens via
`src/transformation/build_schema.py`, which is a separate, full rebuild
step (drops and recreates every table), not part of the scheduler's
incremental cycle. Running the scheduler alone does not update the
warehouse the API/dashboards actually query.

### Monitoring tables
- `pipeline_runs` - one row per scheduler run, with status/timing/row counts
- `pipeline_metrics` - per-run metrics (duplicates_removed, nulls_fixed,
  anomalies_flagged from the cleaning stage)

### Run the scheduler
```bash
python -m src.ingestion.batch_scheduler
```
Test mode (single immediate run, no recurring schedule):
```python
from src.ingestion.batch_scheduler import BatchPipelineScheduler
BatchPipelineScheduler().start(test_mode=True)
```

---

## 3. Real-Time WebSocket Streaming

**File:** `src/ingestion/websocket_streaming.py`

- Generates simulated orders on an interval and writes them to a
  `streaming_orders` table, broadcasting to any connected WebSocket clients.
- **Host/Port**: `ws://localhost:8765` (configurable via `WS_HOST`/`WS_PORT`).

### Run
```bash
python src/ingestion/websocket_streaming.py
```

---

## 4. Adaptive Schema Management

**File:** `src/ingestion/adaptive_schema_manager.py`

### What it actually covers
`AdaptiveSchemaManager.initialize_registry()` registers a schema for
**`transactions` only** - `customers`, `products`, `stores`, `inventory`,
`shipments`, `web_clickstream` have no registered schema, so
`detect_schema_changes()` always returns `([], [])` for those 6 tables
(nothing to compare against). If you need drift detection on other
tables, `initialize_registry()` needs entries added for them.

### Confidence scoring
`_calculate_confidence()` combines null ratio, uniqueness ratio, and
whether the column is non-`object` dtype into a 0.0-1.0 score.

### Noise reduction strategy
| Scenario | Action | Threshold |
|----------|--------|-----------|
| ≤3 changes, all high-confidence | Auto-approve | all ≥0.75 |
| Mixed confidence | Manual review queue | some <0.75 |
| >5 low-confidence changes | Quarantine all | likely corrupt data |

### Tracking tables
`schema_change_log`, `schema_approval_queue` - both created by
`initialize_registry()`.

### Is this wired into the batch pipeline?
**Not automatically.** `AdaptiveSchemaManager` and `BatchIngestionPipeline`
are two separate classes today; `batch_scheduler.py` constructs and
initializes a schema manager at the start of each run mainly so its
tracking tables exist, but `BatchIngestionPipeline.run_for_table()`
doesn't call into it per-row. `src/verify_runtime.py` is the one place
that exercises `detect_schema_changes()` directly, with a hand-built test
DataFrame.

---

## 5. Data quality & monitoring

### Quarantine system
`data/quarantine/{table}_quarantine_{timestamp}.csv`, with a
`quarantine_reason` column - real, but currently produces no rows in
practice since no table has required columns configured (see section 1).

### Pipeline monitoring
```bash
streamlit run src/app_enhanced.py
```
Tab 4 (Pipeline Monitoring) reads real data from `pipeline_runs`.

---

## 6. Integration with the transformation/storage layer

Accurate order of operations for a full rebuild:

```
data_generator.py (Faker)
    v
data/raw/*.csv
    v
data_cleaning.py -> transactions_cleaned.parquet, docs/DATA_QUALITY.md
    v
build_schema.py
    - drops/recreates dim_customer, dim_product, dim_store, dim_date
    - loads fact_sales from transactions_cleaned.parquet
    - calls populate_inventory() -> fact_inventory
    - calls populate_shipments() -> fact_shipments
    v
data/warehouse/retail.duckdb (the tables the API/dashboards query)
    v
access_control.py's create_rbac_views() (also run at API startup)
    v
Analytics (kpi.py) & ML (ml_predictive_engine.py)
```

`partitioning.py` is a side branch off `fact_sales` (writes a partitioned
Parquet copy), not a step in this main chain - nothing downstream reads
from the partitioned copy.

---

## 7. Environment variables

Set via `.env` (copy `.env.example`) or `src/config.py`:
- `DB_PATH` - path to the DuckDB warehouse (`src/config.py`)
- `RETAILOS_API_KEYS` - role-based API keys for the backend (see
  `docs/STORAGE.md`)
- `WS_HOST`/`WS_PORT` - WebSocket streaming server address

---

## Summary

- **Batch ingestion**: real retry logic, real quarantine mechanism (not
  currently triggered by any configured required columns), real
  Parquet output.
- **Scheduler**: real, automates ingestion/cleaning/partitioning/ML
  retraining - but does not itself rebuild the DuckDB warehouse tables;
  that's a separate manual/scripted step (`build_schema.py`).
- **Real-time streaming**: real, generates and broadcasts simulated orders.
- **Adaptive schema management**: real for the one table it's registered
  for (`transactions`); not wired into the other 6 tables or into the
  batch pipeline's row-level validation.
- **ML retraining**: real, but "retraining" is just re-instantiating
  `MLPredictiveEngine` - there's no separate train-only API and no Prophet
  component to retrain (see `docs/ai_usage_overview.md`).
