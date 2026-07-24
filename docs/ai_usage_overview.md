# AI/ML Usage in RetailOS

## Current AI/ML implementation

This describes what's actually implemented and running today, not an
aspirational target. A previous version of this document claimed Prophet
time-series forecasting, festival detection, and per-product-store
forecast models - none of that exists in the codebase. It's removed below.

---

## 1. ML Predictive Engine

**Location:** `src/intelligence/ml_predictive_engine.py`

Two trained models, both real and both trained on actual `fact_inventory`/
`fact_sales` data (not synthetic/random data - an earlier version of this
engine queried columns that didn't exist in `fact_inventory`, silently
fell back to `np.random`-generated training data, and both models were
effectively meaningless; that's fixed):

### A. Random Forest Stockout Classifier
- **Purpose**: classify stockout risk (Critical/High/Medium/Low)
- **Technology**: `sklearn.ensemble.RandomForestClassifier`
- **Features**: `current_stock` (latest `fact_inventory` snapshot per
  product/store), `avg_sales_7d`/`stddev_sales_7d` (derived from
  `fact_sales`, despite the "_7d" name - it's actually an all-time average,
  not a rolling 7-day window; naming kept for backward compatibility with
  downstream code, worth renaming if you touch this file again),
  `category_encoded` (a label-encoding of `dim_product.category`, kept
  stable between training and prediction via `MLPredictiveEngine.category_map`).
- **Output**: risk probability -> `risk_level` string + `ml_confidence` (0-100).

### B. Gradient Boosting Reorder Regressor
- **Purpose**: predict a recommended reorder quantity
- **Technology**: `sklearn.ensemble.GradientBoostingRegressor`
- **Features**: same feature set as the classifier above.
- **Output**: `recommended_reorder` (units).

### What does NOT exist
- **No Prophet forecasting.** `prophet` was previously listed in
  `requirements.txt` despite never being imported anywhere in `src/` -
  removed, since installing it (a heavy dependency) for zero actual use
  just slowed down a fresh `pip install` for no benefit. There is no
  per-product-store demand forecast, no
  festival/holiday detection, no confidence-interval forecast.
- **No `train_stockout_classifier()`/`train_reorder_amount_regressor()`/
  `train_demand_forecaster()` methods.** `MLPredictiveEngine` trains both
  real models automatically inside `__init__` via a private `_train_models()`
  - "retraining" just means constructing a new instance (see
  `src/ingestion/batch_scheduler.py`'s `run_ml_retraining()`).

---

## 2. ML Reasoning & explainability

### `ml_reasoning_log` table
Actual schema (see `MLPredictiveEngine._ensure_runtime_tables`):
`id, timestamp, model_name, product_id, store_id, prediction, confidence, explanation_json`.

`prediction` is the recommended reorder quantity; `confidence` is the risk
probability (0-1); `explanation_json` is a JSON string with
`risk_level`, `ml_confidence` (0-100), `current_stock`, `avg_daily_demand`,
`volatility_cv`. Every call to `predict_stockout_with_explanation()`
inserts one row here (`MLPredictiveEngine._log_decision`).

There is no `prophet_7d_forecast`, `days_remaining_forecast`,
`optimal_reorder_qty`, or `demand_volatility_cv` *column* on this table -
an earlier version of `src/app_enhanced.py` queried those as if they were
columns; they aren't, and those queries always failed silently (caught by
a bare `try/except`). That's fixed - see below.

### Streamlit dashboard
**Location:** `src/app_enhanced.py` (the canonical live dashboard - two
duplicate dashboards, `src/app_websocket.py` and
`dashboards/live_stream_dashboard.py`, were deleted as they added no
unique features and had the same schema mismatch bugs).

- **Tab 1** (Live Intelligence): stockout risk alerts, computed by parsing
  `explanation_json` per row and filtering to `risk_level` in
  `{High, Critical}`. Shows a `days_remaining` estimate computed as
  `current_stock / avg_daily_demand` - a simple runway calculation, not a
  forecast.
- **Tab 2** (ML Reasoning Explorer): drill into any logged prediction,
  parses `explanation_json` for the factor chart. No Prophet
  upper/lower-bound section (removed - there was never a real forecast
  behind those numbers).

---

## 3. Frontend integration

### Current status: wired, not a placeholder
`getTopProductPairs()` and `getAIDecisions()` (in
`frontend/src/services/api.ts`) call real, working endpoints:
- `/api/kpi/top-product-pairs` -> `get_top_product_pairs()` in
  `src/analytics/kpi.py`: real market-basket analysis (co-occurrence,
  confidence, lift) over `fact_sales`, approximating a "basket" as
  everything a customer bought on the same day.
- `/api/kpi/ai-decisions` -> `get_ai_decisions()`: reads real rows from
  `ml_reasoning_log` (parses `explanation_json`), returns `[]` gracefully
  if the log is empty or the table doesn't exist yet.

Both endpoints require an `X-API-Key` header with at least the `analyst`
role - see `docs/STORAGE.md`.

`frontend/src/components/dashboard/ProductPairsTable.tsx` and the
existing `AIDecisionFeed.tsx` are now both rendered on the main dashboard
(`frontend/src/app/page.tsx`) - a previous version of this page never
called either function and showed a static "Product Insights - Coming
soon..." placeholder instead, despite the types, API functions, and
`AIDecisionFeed` component all already existing. That's fixed.

---

## 4. What's active vs. not implemented

**Implemented and real:**
1. Random Forest stockout risk classification (trained on real data)
2. Gradient Boosting reorder quantity prediction (trained on real data)
3. ML reasoning logging with a JSON explanation per prediction
4. Streamlit dashboard reading real `ml_reasoning_log` rows
5. Market basket analysis (`get_top_product_pairs`)
6. AI decision feed wired end-to-end: model -> log -> API -> Next.js UI

**Not implemented (despite being mentioned in older docs/labels):**
1. Prophet or any other time-series demand forecasting
2. Festival/holiday-aware seasonality detection
3. Per-store filtering for the `store_manager` role (see `docs/STORAGE.md`)

---

## 5. How to use the AI features

### Train the models
```bash
python src/intelligence/ml_predictive_engine.py
```
Trains the classifier and regressor against the current warehouse. There
is no `models/` directory persistence step - the models live in memory
for the lifetime of the `MLPredictiveEngine` instance (Streamlit session,
API process, or this one-off script run); nothing is saved to disk today.

### Generate a prediction
```python
from src.intelligence.ml_predictive_engine import MLPredictiveEngine

engine = MLPredictiveEngine()
result = engine.predict_stockout_with_explanation(product_id="P0011", store_id="ST033")

# Returns (or None if that product/store has no fact_inventory row):
# {
#     "recommended_reorder": 6,
#     "confidence": 1.0,  # risk probability, 0-1
#     "explanation": {
#         "risk_level": "Critical",
#         "ml_confidence": 100.0,
#         "current_stock": 0.0,
#         "avg_daily_demand": 3.2,
#         "volatility_cv": 0.41,
#     }
# }
```
Each call also inserts a row into `ml_reasoning_log`.

### View in the Streamlit dashboard
```bash
streamlit run src/app_enhanced.py
```
Tab 1 for live risk alerts, Tab 2 to drill into any logged prediction.

### View in the Next.js dashboard
```bash
cd frontend && npm run dev
```
"Frequently Bought Together" and "AI Decision Feed" panels are on the main
page, both backed by the real endpoints above.
