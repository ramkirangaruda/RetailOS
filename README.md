# RetailOS - Intelligent Retail Analytics Platform

A production-ready retail analytics platform with ML-powered inventory optimization, real-time streaming, and adaptive schema management.

---

## 🚀 Quick Start Guide

Follow these steps to get RetailOS running from scratch to full outputs.

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **Git**

---

## Step 1: Clone & Setup

```bash
# Clone the repository
git clone https://github.com/ramkirangaruda/RetailOS.git
cd RetailOS

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

---

## Step 2: Generate Sample Data

```bash
# Generate realistic Indian retail data
python src/data_generator.py
```

**Output:** Creates CSV files in `data/raw/`:
- `customers.csv`
- `products.csv`
- `stores.csv`
- `inventory.csv`
- `transactions.csv`
- `shipments.csv`
- `web_clickstream.csv`

---

## Step 3: Build Data Warehouse

```bash
# Run ETL pipeline to create DuckDB warehouse
python src/storage/warehouse_builder.py
```

**Output:** Creates `data/warehouse/retail.duckdb` with:
- Fact tables: `fact_sales`, `fact_inventory`
- Dimension tables: `dim_product`, `dim_store`, `dim_customer`, `dim_date`
- RBAC views for role-based access

---

## Step 4: Train ML Models

```bash
# Train all ML models
python src/intelligence/ml_predictive_engine.py
```

**Output:** Creates models in `models/`:
- `stockout_classifier.pkl` - Random Forest for risk classification
- `reorder_regressor.pkl` - Gradient Boosting for reorder quantities
- `prophet_{product}_{store}.pkl` - Prophet models for demand forecasting

**Expected:** ~85% accuracy on stockout classifier, R² > 0.7 on regressor

---

## Step 5: Start Backend API

```bash
# Start FastAPI server
uvicorn src.api.server:app --reload
```

**Output:** API running at `http://localhost:8000`

**Auth:** every `/api/kpi/*`, `/api/analyst/*`, `/api/store-manager/*`,
`/api/finance/*`, and `/api/admin/*` route requires an `X-API-Key` header
(role-based access control, see `src/api/auth.py`). `/health` does not.
Demo keys for local development (override via `RETAILOS_API_KEYS` env var,
format `key:role` or `key:role:store_id` for store managers, e.g.
`sm-st007-key:store_manager:ST007`):

| Role | Demo key | Store scope |
|------|----------|-------------|
| analyst | `demo-analyst-key` | - |
| store_manager | `demo-store-manager-key` | `ST007` (see `src/api/auth.py`) |
| finance | `demo-finance-key` | - |
| admin | `demo-admin-key` | - |

**Test endpoints:**
```bash
curl http://localhost:8000/health
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/daily-revenue
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/city-sales
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/customer-distribution
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/stockout-risks

# Role-gated row-level views (masked vs. full PII/profit - see docs/STORAGE.md)
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/analyst/sales
curl -H "X-API-Key: demo-store-manager-key" http://localhost:8000/api/store-manager/sales  # only ST007 rows
curl -H "X-API-Key: demo-finance-key" http://localhost:8000/api/finance/sales
curl -H "X-API-Key: demo-admin-key" http://localhost:8000/api/admin/summary
```

---

## Step 6: Start Frontend Dashboard (Next.js)

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_API_KEY=demo-analyst-key" >> .env.local

# Start development server
npm run dev
```

**Output:** Dashboard running at `http://localhost:3000`

**Features:**
- Daily revenue charts
- City-wise sales performance
- Customer distribution by tier
- Stockout risk analysis
- Dark theme UI

---

## Step 7: Start Streamlit Dashboard (Optional)

```bash
# From project root
streamlit run src/app_enhanced.py
```

**Output:** Streamlit app at `http://localhost:8501`

**Features:**
- Live intelligence dashboard
- ML reasoning explorer
- Schema evolution tracking
- Pipeline monitoring

---

## Step 8: Start Real-Time Streaming (Optional)

```bash
# Start WebSocket server for live orders
python src/ingestion/websocket_streaming.py
```

**Output:** WebSocket server at `ws://localhost:8765`

**What it does:**
- Generates orders every 1-5 seconds
- Writes to `streaming_orders` table
- Broadcasts to connected clients

---

## Step 9: Start Automated Scheduler (Production)

```bash
# Start batch scheduler (runs forever)
python src/ingestion/batch_scheduler.py
```

**What it does:**
- **Every 6 hours:** Batch data ingestion
- **Daily at 2 AM:** ML model retraining
- **Every 30 minutes:** Data quality checks
- **Weekly:** Log cleanup

---

## 📊 Expected Outputs

### 1. Next.js Dashboard (localhost:3000)
- **Revenue Chart:** 30-day trend with total revenue
- **City Sales:** Top cities by revenue with metrics
- **Customer Distribution:** Segmentation by tier and value
- **Stockout Risks:** Top 20 products with movement analysis

### 2. Streamlit Dashboard (localhost:8501)
- **Tab 1:** Live stockout alerts with ML confidence
- **Tab 2:** ML reasoning explorer (current stock / avg daily demand / demand volatility - no forecasting model is implemented)
- **Tab 3:** Schema evolution history
- **Tab 4:** Pipeline performance metrics

### 3. API Endpoints (localhost:8000)
All endpoints (except `/health`) require an `X-API-Key` header - see Step 5 above:
```bash
curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/daily-revenue
# Returns: [{"date": "2026-02-13", "revenue": 125000.50}, ...]

curl -H "X-API-Key: demo-analyst-key" http://localhost:8000/api/kpi/city-sales
# Returns: [{"city": "Mumbai", "total_revenue": 5000000, ...}, ...]
```

### 4. Database Queries
```bash
# Connect to DuckDB
python -c "import duckdb; con = duckdb.connect('data/warehouse/retail.duckdb'); print(con.execute('SELECT COUNT(*) FROM fact_sales').fetchone())"
```

---

## 🛠️ Project Structure

```
RetailOS/
├── data/
│   ├── raw/              # CSV files
│   ├── warehouse/        # DuckDB database
│   └── quarantine/       # Invalid records
├── frontend/             # Next.js dashboard
│   ├── src/
│   │   ├── app/         # Pages
│   │   ├── components/  # React components
│   │   ├── services/    # API layer
│   │   └── types/       # TypeScript types
├── src/
│   ├── api/             # FastAPI server
│   ├── analytics/       # KPI functions
│   ├── ingestion/       # Data pipelines
│   ├── intelligence/    # ML models
│   ├── storage/         # Warehouse builder
│   └── transformation/  # Data cleaning
├── models/              # Trained ML models
└── logs/                # Pipeline logs
```

---

## 🔧 Troubleshooting

### Backend API not responding
```bash
# Check if server is running
curl http://localhost:8000/health

# Restart server
uvicorn src.api.server:app --reload
```

### Frontend shows "No data"
1. Ensure backend is running on port 8000
2. Check `.env.local` has correct API URL and `NEXT_PUBLIC_API_KEY`
3. Verify CORS is enabled in `src/api/server.py`
4. A `401`/`403` in the browser console means the API key is missing, wrong,
   or doesn't have the role a route requires - see Step 5's auth table

### ML models not found
```bash
# Retrain models
python src/intelligence/ml_predictive_engine.py
```

### Database not found
```bash
# Rebuild warehouse
python src/storage/warehouse_builder.py
```

---

## 📚 Key Technologies

- **Backend:** FastAPI, DuckDB, Python
- **Frontend:** Next.js 15, React, TypeScript, Tailwind CSS
- **ML:** Prophet, scikit-learn, pandas
- **Streaming:** WebSocket, asyncio
- **Scheduling:** APScheduler
- **Visualization:** Plotly, Recharts

---

## 🎯 Production Deployment

### Run in Background
```bash
# Backend API
nohup uvicorn src.api.server:app --host 0.0.0.0 --port 8000 &

# Batch Scheduler
nohup python src/ingestion/batch_scheduler.py &

# WebSocket Streaming (optional)
nohup python src/ingestion/websocket_streaming.py &
```

### Build Frontend for Production
```bash
cd frontend
npm run build
npm start
```

---

## 📖 Documentation

- [Architecture](docs/ARCHITECTURE.md) - end-to-end data flow diagram and what's real vs. aspirational
- [Storage & Security](docs/STORAGE.md) - partitioning benchmark (measured, not estimated) and RBAC/access-control implementation
- [Data Quality Report](docs/DATA_QUALITY.md) - auto-generated by `src/transformation/data_cleaning.py`
- [Sample Analytical Dataset](docs/sample_dataset/README.md)
- [AI/ML Usage Overview](docs/ai_usage_overview.md)
- [Data Ingestion Architecture](docs/data_ingestion_overview.md)
- [Backend API Verification](docs/backend_verification.md)
- [Walkthrough](docs/walkthrough.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🙋 Support

For issues or questions, please open an issue on GitHub.

---

**Built with ❤️ for modern retail analytics**
