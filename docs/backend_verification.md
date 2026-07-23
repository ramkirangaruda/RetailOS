# Backend API Verification

Reflects the API as it exists today, verified by actually running it
(`uvicorn src.api.server:app`) and curling every route - not aspirational.
A prior version of this document only covered 4 KPI functions and
predates the auth layer entirely; both are out of date and replaced below.

---

## 1. Authentication (added after the original version of this document)

Every route except `/health` requires an `X-API-Key` header, resolved to
a role by `src/api/auth.py`. See `docs/STORAGE.md` for the full role
matrix and the "what this doesn't cover" scope notes.

Verified behavior:
- No/unknown key -> `401`
- Known key, insufficient role -> `403`
- Known key, sufficient role -> `200` with real data

Demo keys (override via `RETAILOS_API_KEYS` env var):
`demo-analyst-key`, `demo-store-manager-key`, `demo-finance-key`,
`demo-admin-key`.

---

## 2. KPI functions in `src/analytics/kpi.py`

| Function | Verified? | Notes |
|----------|-----------|-------|
| `get_daily_revenue()` | ✅ | `fact_sales` join `dim_date`, last 30 days |
| `get_city_sales()` | ✅ | `fact_sales` join `dim_store` |
| `get_customer_distribution()` | ✅ | Real per-customer CLV (aggregated per customer, then averaged per city) and real day counts via `dim_date` (fixed a bug where `date_key` integers like `20240301` were subtracted directly, which is not a valid day count across month boundaries) |
| `get_stockout_risks()` | ✅ | Sell-through velocity proxy from `fact_sales`/`dim_product` - does not use `fact_inventory` (see `get_inventory_turnover()` for that) |
| `get_inventory_turnover()` | ✅ | Real turnover ratio using `fact_inventory.stock_level` |
| `get_delivery_performance()` | ✅ | Real avg/min/max delivery time + on-time % from `fact_shipments` (previously this was a hardcoded `AVG(1)` placeholder that never touched shipment data at all) |
| `get_top_product_pairs()` | ✅ | Real market-basket analysis (co-occurrence/confidence/lift); previously returned `[]` unconditionally |
| `get_ai_decisions()` | ✅ | Real rows from `ml_reasoning_log`, parsed from `explanation_json`; previously returned `[]` unconditionally |

---

## 3. API endpoints in `src/api/server.py`

```python
# Aggregate KPIs (role >= analyst)
GET /api/kpi/daily-revenue
GET /api/kpi/city-sales
GET /api/kpi/customer-distribution
GET /api/kpi/stockout-risks
GET /api/kpi/inventory-turnover
GET /api/kpi/delivery-performance
GET /api/kpi/top-product-pairs
GET /api/kpi/ai-decisions

# Row-level views with masked/full PII (role-gated per view)
GET /api/analyst/sales   # role >= analyst, masked phone/email
GET /api/store-manager/sales  # role >= store_manager, masked, filtered to the caller's assigned store
GET /api/finance/sales   # role >= finance, unmasked + profit
GET /api/admin/summary   # role >= admin, aggregate row counts/revenue

GET /health  # no auth required
```

---

## 4. CORS configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
`allow_origins=["*"]` is broad (fine for local dev; would want to scope
this to the actual frontend origin(s) for a real deployment).

---

## 5. Database connections

Each request gets a short-lived connection via
`src.storage.warehouse.get_connection()` (a context manager, closes on
exit) - not one long-lived shared connection. Read paths use
`read_only=True`. The RBAC views (`analyst_sales`/`finance_sales`/
`admin_all`) are (re)created once at API startup via a `lifespan` hook,
non-fatal if it fails (e.g. warehouse not built yet in a fresh environment).

---

## 6. Frontend contract compliance

| TypeScript interface | Backend function | Rendered in `page.tsx`? |
|---|---|---|
| `DailyRevenue` | `get_daily_revenue()` | ✅ |
| `CitySales` | `get_city_sales()` | ✅ |
| `CustomerDistribution` | `get_customer_distribution()` | ✅ |
| `StockoutRisk` | `get_stockout_risks()` | ✅ |
| `ProductPair` | `get_top_product_pairs()` | ✅ (previously the types/API function/component all existed but were never wired into `page.tsx` - a "Coming soon..." placeholder sat there instead; fixed) |
| `AIDecision` | `get_ai_decisions()` | ✅ (same - `AIDecisionFeed.tsx` existed but was never rendered; fixed) |

`inventory-turnover` and `delivery-performance` have no frontend
TypeScript type or component yet - they're real, working endpoints, just
not surfaced in the Next.js dashboard.

---

## 7. Verifying it yourself

```bash
uvicorn src.api.server:app --reload
curl http://localhost:8000/health
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/daily-revenue
curl -H "X-API-Key: demo-finance-key" http://localhost:8000/api/finance/sales
curl -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/kpi/daily-revenue  # expect 401, no key
```

---

## Summary

The API surface described here has been run and curled directly, not just
read from source - every status code and data shape above reflects an
actual observed response, not an assumption about what the code should do.
