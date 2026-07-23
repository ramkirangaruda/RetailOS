from fastapi import FastAPI
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

app = FastAPI()

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

@app.get("/api/kpi/daily-revenue")
def daily_revenue():
    return get_daily_revenue()

@app.get("/api/kpi/city-sales")
def city_sales():
    return get_city_sales()

@app.get("/api/kpi/customer-distribution")
def customer_distribution():
    return get_customer_distribution()

@app.get("/api/kpi/stockout-risks")
def stockout_risks():
    return get_stockout_risks()

@app.get("/api/kpi/inventory-turnover")
def inventory_turnover():
    return get_inventory_turnover()

@app.get("/api/kpi/delivery-performance")
def delivery_performance():
    return get_delivery_performance()

@app.get("/api/kpi/top-product-pairs")
def top_product_pairs():
    return get_top_product_pairs()

@app.get("/api/kpi/ai-decisions")
def ai_decisions():
    return get_ai_decisions()
