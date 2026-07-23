# RetailOS Storage Architecture

## Overview

RetailOS stores its warehouse in a single DuckDB file
(`data/warehouse/retail.duckdb`), with an additional partitioned Parquet
copy of `fact_sales` for date/region-based access. Role-based access
control and PII masking are implemented at the application layer (the
FastAPI backend), not inside DuckDB itself - DuckDB is an embedded,
single-file database with no native multi-user GRANT/REVOKE system, so
that's the boundary where enforcement actually happens. This document
describes what's implemented today, with real measured numbers, and is
explicit about what's aspirational guidance for a production deployment
versus what actually exists in this codebase.

## Partitioning Strategy

### Date + Region Partitioning
- **Implementation**: `src/storage/partitioning.py` reads `fact_sales`
  (joined to `dim_date`/`dim_store` for the actual date and region), and
  writes it to Parquet partitioned by `date_partition` (YYYY-MM-DD) and
  `region`.
- **Location**: `data/warehouse/partitioned/fact_sales/`
- **Run it**: `python src/storage/partitioning.py` (writes the partitioned
  copy, then runs `benchmark_query()` for a real timing comparison against
  the un-partitioned DuckDB table).

### Partition Structure (actual, from a real run)
```
data/warehouse/partitioned/fact_sales/
├── date_partition=2024-01-01/
│   ├── region=East/
│   ├── region=North/
│   ├── region=South/
│   ├── region=Unknown/
│   └── region=West/
├── date_partition=2024-01-02/
│   └── ...
...
```
182 distinct dates × up to 5 regions produced **1,456 Parquet files
totaling ~25MB** for this dataset (98,670 sales rows).

### Benchmark Results (measured, not estimated)
Ran `benchmark_query()` three times against the real warehouse
(98,670 rows in `fact_sales`) for a single-date filter (`date_key = 20240325`):

| Run | Unpartitioned (native DuckDB table) | Partitioned (Parquet glob) |
|-----|--------------------------------------|----------------------------|
| 1   | 0.003s | 0.251s |
| 2   | 0.002s | 0.165s |
| 3   | 0.002s | 0.160s |

**Partitioning is ~60-100x *slower* than the plain DuckDB table scan at
this data volume**, not faster. This isn't a bug in the implementation -
partition pruning genuinely does skip the 1,451 non-matching files - it's
that opening ~5 tiny Parquet files (one per region, for one date) still
costs more (file-system stat calls, per-file schema/metadata read) than
DuckDB just scanning its own ~98K-row native columnar table directly,
which fits comfortably in memory and needs no file-open overhead at all.

We also tested a coarser grain (partition by month instead of exact date,
24 files instead of 1,456): still slower than the native table scan
(0.061s vs 0.001s) for the same reason - the fixed cost of reading Parquet
files via `read_parquet(glob)` dominates until the *un*-partitioned scan
itself becomes expensive, which only happens at data volumes far larger
than this demo dataset (realistically: many GBs / hundreds of millions of
rows, where the partitioned dataset no longer fits in a single fast native
table and full-scan cost, not file-open cost, is the bottleneck). At
production data volumes, this partitioning strategy would be expected to
help; at this dataset's size, it measurably doesn't, and the honest
number is the useful thing to report.

### Benchmark Methodology
- **Test Environment**: whatever machine `python src/storage/partitioning.py`
  was actually run on (local dev machine, not a fixed spec) - this is
  measured, so "environment" is just "this repo's checkout," not a
  standardized benchmark rig.
- **Test Data**: 98,670 real `fact_sales` rows, 5 regions, Jan-Jun 2024.
- **Query**: `SELECT SUM(revenue) FROM fact_sales WHERE date_key = 20240325`
  vs. the equivalent `read_parquet(...) WHERE date_partition = '2024-03-25'`.
- **Metrics**: single timed run per call to `benchmark_query()`, no
  warm/cold cache control - repeat runs shown above for variance, not a
  formal statistical benchmark.

## RBAC Role Matrix

Four roles, least to most privileged: `analyst` < `store_manager` <
`finance` < `admin` (see `src/api/auth.py`'s `ROLE_HIERARCHY`).

| Role | fact_sales access | PII | Financial data | Notes |
|------|--------------------|-----|-----------------|-------|
| **analyst** | `analyst_sales` view via `/api/analyst/sales` | Masked (phone/email) | None (no cost/profit) | |
| **store_manager** | `store_manager_sales` view via `/api/store-manager/sales`, **filtered to the caller's assigned store** | Masked | None | Store assignment comes from the API key itself (`RETAILOS_API_KEYS` format `key:store_manager:STORE_ID`, e.g. `sm-st007-key:store_manager:ST007`) - verified end-to-end: a key assigned to `ST007` only ever gets `ST007` rows back. A `store_manager` key with no store assigned would get unfiltered results (same as a higher-privileged caller) - configure store keys with a store_id to avoid that. |
| **finance** | `finance_sales` view via `/api/finance/sales` | Unmasked (name/email/phone) | Full, including per-line `profit` | |
| **admin** | `admin_all` view via `/api/admin/summary` | N/A | Aggregate only | Not literally "full access to all dimensions" - it's a summary view, not row-level access to every table. |

### How enforcement actually works
1. Every `/api/kpi/*`, `/api/analyst/*`, `/api/store-manager/*`,
   `/api/finance/*`, `/api/admin/*` route in `src/api/server.py` depends on
   `require_role(...)` (or `require_identity(...)` for the store-scoped
   route) from `src/api/auth.py`.
2. The caller sends an `X-API-Key` header. `src/api/auth.py` resolves it
   to an `Identity(role, store_id)` via the `RETAILOS_API_KEYS` env var
   (`key:role` or `key:role:store_id` entries, comma-separated), falling
   back to fixed demo keys if unset.
3. A route's `require_role("finance")` rejects with `401` (no/unknown key)
   or `403` (known key, insufficient role) before the handler ever runs.
4. Handlers for `/api/analyst/sales`, `/api/store-manager/sales`,
   `/api/finance/sales`, `/api/admin/summary` query the matching DuckDB
   view (`src/analytics/secure_views.py`); `/api/store-manager/sales`
   additionally joins `dim_store` and filters by the caller's
   `identity.store_id`. A `finance`-only column like `profit` is only ever
   selected when the caller already passed the role check for that route.

### What this does *not* cover
- **Anyone with direct access to `data/warehouse/retail.duckdb`** (a copy
  of the file, a notebook, a BI tool connecting to it directly) bypasses
  all of the above and can query `fact_sales`/`dim_customer` unmasked.
  DuckDB has no native per-connection user/permission system to prevent
  this - the mitigation is keeping the file itself off of anything except
  the API/Streamlit processes (e.g. the Docker volume it lives in), not a
  database-level control.
- **The demo API keys are plaintext, unexpiring, and not per-user** - see
  `src/api/auth.py`'s module docstring. This demonstrates the access
  control mechanism working end-to-end; it is not a production credential
  system (no hashing, rotation, audit log of who used which key, etc.).
- **No request/access audit logging exists.** A previous version of this
  document claimed "access logs for all PII data requests" and "automated
  alerts for suspicious access patterns" - neither is implemented. If you
  need that, it would mean adding a logging middleware that records
  (role, route, timestamp) per request, which doesn't exist today.

## PII Masking Strategy

### Phone Number Masking
**Logic**: `CONCAT('XXXXX-', RIGHT(phone, 4))`

**Examples**:
- Original: `+91-9876543210` → Masked: `XXXXX-3210`
- Original: `080-12345678` → Masked: `XXXXX-5678`

**Rationale**: preserves the last 4 digits (useful for customer-service
lookups) while hiding the rest.

### Email Address Masking
**Logic**: `CONCAT(LEFT(email, 1), '***@', SPLIT_PART(email, '@', 2))`

**Examples**:
- Original: `john.doe@example.com` → Masked: `j***@example.com`
- Original: `support@company.org` → Masked: `s***@company.org`

**Rationale**: keeps the domain (useful for coarse business analytics,
e.g. free-mail vs. corporate domains) while hiding the local part.

### Implementation
```sql
-- src/storage/access_control.py: create_rbac_views()
CREATE VIEW analyst_sales AS
SELECT
    fs.sale_id, fs.date_key, fs.product_key, fs.store_key,
    fs.quantity, fs.revenue,
    CONCAT('XXXXX-', RIGHT(dc.phone, 4)) as phone_masked,
    CONCAT(LEFT(dc.email, 1), '***@', SPLIT_PART(dc.email, '@', 2)) as email_masked,
    dc.city as customer_city
FROM fact_sales fs
JOIN dim_customer dc ON fs.customer_key = dc.customer_key;
```

`create_rbac_views()`/`verify_schema()` are plain functions that take an
existing connection and raise on failure - they're called from
`src/api/server.py`'s FastAPI `lifespan` hook on startup (non-fatal if it
fails, e.g. warehouse not built yet), and can also be run standalone via
`python src/storage/access_control.py` for CLI-style verification output.

## What's aspirational, not implemented

Kept here deliberately (rather than deleted) so it's clear what a
production hardening pass would still need to add - none of the following
exists in this codebase today:
- Encryption at rest/in transit beyond whatever the host OS/filesystem and
  HTTPS termination in front of the API would normally provide.
- VPN/network-level access restrictions, firewall rules.
- Multi-factor authentication.
- Encrypted backups, backup rotation/retention policy.
- Materialized views for KPI aggregations (KPIs are computed on the fly
  in `src/analytics/kpi.py` on every request).
- Any audit log of who accessed what, when.
- Automatic incident-response procedures for a data breach.

## Troubleshooting

### Partitioned queries are slower than expected
This is expected at this dataset's size - see the Benchmark Results
section above. Don't "fix" it by tuning the partition grain further; the
overhead is inherent to reading many small Parquet files vs. one native
DuckDB table at this row count.

### 401 from the API
Missing or unrecognized `X-API-Key` header. See the demo keys in
`src/api/auth.py` or the table in `README.md`'s Step 5.

### 403 from the API
Valid key, but its role is below what that route requires (see the Role
Matrix above).

### PII shows up unmasked where you didn't expect it
Check which view/endpoint you're querying - `finance_sales` and
`/api/finance/sales` are *supposed* to show unmasked PII and profit to
`finance`/`admin` roles. If an `analyst`-role response shows unmasked PII,
that's a real bug: `analyst_sales` should always be masked - file it as
one.
