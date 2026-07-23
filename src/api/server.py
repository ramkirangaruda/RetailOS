from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.analytics.kpi import (
    get_daily_revenue,
    get_city_sales,
    get_customer_distribution,
    get_stockout_risks,
    get_inventory_turnover,
    get_delivery_performance,
    get_top_product_pairs,
    get_ai_decisions
)
from src.analytics.secure_views import get_analyst_sales, get_finance_sales, get_admin_summary
from src.api.auth import require_role
from src.storage.access_control import create_rbac_views
from src.storage.warehouse import get_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the RBAC/PII-masking views exist before any request comes in.
    # Non-fatal if it fails (e.g. warehouse not built yet in a fresh
    # environment) - only /api/analyst/*, /api/finance/*, /api/admin/*
    # depend on these views; the plain /api/kpi/* routes don't.
    try:
        with get_connection(read_only=False) as con:
            create_rbac_views(con)
    except Exception as e:
        print(f"Warning: could not create RBAC views at startup: {e}")
    yield


app = FastAPI(lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------------------------------------------------------------------
# Aggregate KPIs - no PII, no cost/profit. Requires at least "analyst".
# ---------------------------------------------------------------------

@app.get("/api/kpi/daily-revenue")
def daily_revenue(role: str = Depends(require_role("analyst"))):
    return get_daily_revenue()

@app.get("/api/kpi/city-sales")
def city_sales(role: str = Depends(require_role("analyst"))):
    return get_city_sales()

@app.get("/api/kpi/customer-distribution")
def customer_distribution(role: str = Depends(require_role("analyst"))):
    return get_customer_distribution()

@app.get("/api/kpi/stockout-risks")
def stockout_risks(role: str = Depends(require_role("analyst"))):
    return get_stockout_risks()

@app.get("/api/kpi/inventory-turnover")
def inventory_turnover(role: str = Depends(require_role("analyst"))):
    return get_inventory_turnover()

@app.get("/api/kpi/delivery-performance")
def delivery_performance(role: str = Depends(require_role("analyst"))):
    return get_delivery_performance()

@app.get("/api/kpi/top-product-pairs")
def top_product_pairs(role: str = Depends(require_role("analyst"))):
    return get_top_product_pairs()

@app.get("/api/kpi/ai-decisions")
def ai_decisions(role: str = Depends(require_role("analyst"))):
    return get_ai_decisions()

# ---------------------------------------------------------------------
# Row-level views with masked/full PII and financials. Role-gated per
# src/storage/access_control.py's view definitions.
# ---------------------------------------------------------------------

@app.get("/api/analyst/sales")
def analyst_sales(limit: int = 100, role: str = Depends(require_role("analyst"))):
    """Sales with customer phone/email masked, no cost/profit."""
    return get_analyst_sales(limit)

@app.get("/api/finance/sales")
def finance_sales(limit: int = 100, role: str = Depends(require_role("finance"))):
    """Full sales detail: unmasked customer PII and per-line profit."""
    return get_finance_sales(limit)

@app.get("/api/admin/summary")
def admin_summary(role: str = Depends(require_role("admin"))):
    """System-wide row counts and revenue summary."""
    return get_admin_summary()
