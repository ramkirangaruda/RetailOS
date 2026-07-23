# RetailOS Architecture

End-to-end data flow, from raw source files through to the dashboards and
API consumers. This reflects what the code in this repo actually does, not
an idealized target state - see the inline notes for known gaps.

## Data flow

```mermaid
flowchart TD
    subgraph Sources["Sources"]
        FAKER["src/data_generator.py\n(Faker-generated CSVs)"]
        RAWCSV["data/raw/*.csv\ncustomers, products, stores,\ninventory, transactions, shipments,\nweb_clickstream"]
        WSCLIENTS["Simulated live orders"]
    end

    FAKER --> RAWCSV

    subgraph Ingestion["Ingestion (src/ingestion/)"]
        BATCH["batch_pipeline.py\nCSV -> validate -> quarantine/parquet\n(retry with backoff)"]
        SCHEMA["adaptive_schema_manager.py\nschema drift detection\n(transactions table only today)"]
        WS["websocket_streaming.py\nnear-real-time order feed\n(ws://localhost:8765)"]
        SCHED["batch_scheduler.py (APScheduler)\nruns batch ingestion every 6h,\nML retrain daily, DQ checks every 30m"]
    end

    RAWCSV --> BATCH
    BATCH --> SCHEMA
    WSCLIENTS --> WS
    SCHED --> BATCH

    subgraph Transform["Transformation (src/transformation/)"]
        CLEAN["data_cleaning.py\ndedup, null-fill, negative-price fix,\nfuture-date filter, anomaly flagging\n-> transactions_cleaned.parquet\n-> docs/DATA_QUALITY.md"]
        BUILDSCHEMA["build_schema.py\ndrops/rebuilds star schema,\nloads dims + fact_sales,\nthen calls the two loaders below"]
        SCD["scd_type2.py\nSCD Type 2 on dim_customer.city\n(idempotent, verified no dup currents)"]
        POPINV["storage/populate_inventory.py\ninventory.csv -> fact_inventory\n(fixes header/data column mismatch)"]
        POPSHIP["storage/populate_shipments.py\nshipments.csv -> fact_shipments\n(joins via fact_sales.sale_id)"]
    end

    BATCH --> CLEAN
    CLEAN --> BUILDSCHEMA
    RAWCSV --> BUILDSCHEMA
    BUILDSCHEMA --> POPINV
    BUILDSCHEMA --> POPSHIP
    BUILDSCHEMA -.SCD2 applied post-load.-> SCD

    subgraph Warehouse["Storage (data/warehouse/retail.duckdb)"]
        DIMS["dim_customer (SCD2), dim_product,\ndim_store, dim_date, dim_external_events (unused)"]
        FACTS["fact_sales, fact_inventory,\nfact_shipments"]
        PART["storage/partitioning.py\nfact_sales -> partitioned Parquet\n(date + region) - see docs/STORAGE.md:\nmeasured SLOWER than native table\nat this data volume"]
        RBAC["storage/access_control.py\nanalyst_sales / store_manager_sales /\nfinance_sales / admin_all views\n(PII masking, profit gating)"]
        RUNTIME["ml_reasoning_log, pipeline_runs,\npipeline_metrics, schema_change_log,\nschema_approval_queue"]
    end

    POPINV --> FACTS
    POPSHIP --> FACTS
    BUILDSCHEMA --> DIMS
    BUILDSCHEMA --> FACTS
    FACTS --> PART
    DIMS --> RBAC
    FACTS --> RBAC
    SCHED --> RUNTIME
    SCHEMA --> RUNTIME

    subgraph Analytics["Analytics (src/analytics/, src/intelligence/)"]
        KPI["kpi.py + kpi_queries.sql\nrevenue, city sales, CLV, inventory\nturnover, delivery performance,\nmarket basket, stockout risk"]
        ML["intelligence/ml_predictive_engine.py\nRandomForest (stockout risk) +\nGradientBoosting (reorder qty),\ntrained on fact_inventory/fact_sales.\nNo Prophet/forecasting model exists\ndespite requirements.txt listing it."]
    end

    DIMS --> KPI
    FACTS --> KPI
    DIMS --> ML
    FACTS --> ML
    ML --> RUNTIME

    subgraph API["API layer (src/api/)"]
        AUTH["auth.py\nX-API-Key -> role\n(analyst < store_manager < finance < admin)"]
        SERVER["server.py (FastAPI)\n/api/kpi/*  (role >= analyst)\n/api/analyst/sales, /api/finance/sales,\n/api/admin/summary (role-gated,\nqueries the RBAC views above)"]
    end

    KPI --> SERVER
    RBAC --> SERVER
    AUTH --> SERVER

    subgraph Consumers["Consumers"]
        NEXT["frontend/ (Next.js)\nRevenueChart, CitySalesChart,\nCustomerChart, StockoutTable,\nAIDecisionFeed"]
        STREAMLIT["src/app_enhanced.py (Streamlit)\nLive Intelligence, ML Reasoning,\nSchema Evolution, Pipeline Monitoring,\nApproval Queue (placeholder)"]
    end

    SERVER -->|"X-API-Key header"| NEXT
    RUNTIME --> STREAMLIT
    Warehouse --> STREAMLIT
```

## Component notes (what's real vs. what's a known gap)

| Layer | Status |
|-------|--------|
| Batch ingestion retry/backoff | Real - `batch_pipeline.py`'s `_read_with_retries` genuinely retries with exponential backoff. |
| Schema evolution detection | Partial - only registered for the `transactions` table; other 6 tables have no schema drift detection. |
| Near-real-time ingestion | Real - `websocket_streaming.py` genuinely streams simulated orders. |
| Data cleaning | Real - dedup, null-fill, negative-price fix, anomaly flagging all genuinely run and produce `docs/DATA_QUALITY.md` as evidence. |
| SCD Type 2 | Real - `scd_type2.py` correctly expires/inserts customer city-change history, with idempotency checks. |
| Star schema build | Real, and now also populates `fact_inventory`/`fact_shipments` (previously left empty). |
| Partitioning | Implemented and does prune correctly, but measured *slower* than a plain DuckDB scan at this data volume - see `docs/STORAGE.md` for real numbers and why. |
| RBAC / PII masking | Real, and now actually enforced at the API layer via `src/api/auth.py` - not just decorative views. Scope boundary: doesn't cover direct access to the `.duckdb` file itself (see `docs/STORAGE.md`). |
| ML stockout/reorder models | Real - trained on actual `fact_inventory`/`fact_sales` data (previously silently fell back to random dummy data because it queried columns that didn't exist). |
| Demand forecasting (Prophet) | **Not implemented.** `prophet` is listed in `requirements.txt` and mentioned in older docs/README text, but never imported anywhere in `src/`. Any "forecast" language elsewhere refers to a simple current-stock/avg-daily-demand runway estimate, not a real time-series model. |
| API auth | Real, demo-scoped (see `src/api/auth.py`'s docstring) - not production-grade credential management. |
| Dashboards | `src/app_enhanced.py` is the canonical Streamlit dashboard (two prior duplicates deleted). Its Schema Evolution and Pipeline Monitoring tabs are fully working; its ML tabs were rewritten to match the real `ml_reasoning_log` schema. `frontend/` (Next.js) is the canonical web dashboard (a stale `retailos-frontend/` duplicate was deleted). |

## Still missing from the original assignment spec
- A polished, non-Mermaid visual diagram (this file satisfies "architecture
  diagram" via a Mermaid flowchart, which GitHub renders inline - no
  separate image tool was used).
- A committed sample of the final analytical tables - see
  `docs/sample_dataset/` (added alongside this file).
