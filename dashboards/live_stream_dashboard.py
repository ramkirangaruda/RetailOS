import streamlit as st
import duckdb
import pandas as pd
import time

DB_PATH = "data/warehouse/retail.duckdb"

# Page config & Custom CSS
st.set_page_config(page_title="RetailOS Live Command Center", layout="wide")

# Apply custom styling with the requested color palette
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
        background-color: #F0F0DB;
        color: #30364F;
        font-family: 'Outfit', sans-serif;
    }}
    
    .main-title {{
        color: #30364F;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        border-bottom: 3px solid #E1D9BC;
        padding-bottom: 10px;
    }}
    
    .metric-container {{
        background: #30364F;
        color: #F0F0DB;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 10px 20px rgba(48, 54, 79, 0.15);
        margin: 10px 0;
    }}
    
    .metric-value {{
        font-size: 2.2rem;
        font-weight: 700;
    }}
    
    .metric-label {{
        font-size: 1rem;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    
    .section-header {{
        color: #30364F;
        font-weight: 600;
        font-size: 1.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    
    .alert-card {{
        background: white;
        border: 1px solid #E1D9BC;
        border-left: 6px solid #30364F;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        transition: transform 0.2s;
    }}
    
    .alert-card:hover {{
        transform: translateX(5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }}
    
    .alert-critical {{
        border-left-color: #d32f2f;
    }}
    
    .alert-high {{
        border-left-color: #ef6c00;
    }}
    
    [data-testid="stMetricValue"] {{
        color: #30364F;
    }}
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">🚀 RetailOS Live Command Center</h1>', unsafe_allow_html=True)

@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH)

con = get_connection()

def get_live_metrics():
    total_orders = con.execute("SELECT COUNT(*) FROM streaming_orders").fetchone()[0]
    revenue = con.execute("""
        SELECT COALESCE(SUM(price * quantity), 0)
        FROM streaming_orders
        WHERE DATE(timestamp) = CURRENT_DATE
    """).fetchone()[0]
    return total_orders, revenue

def get_recent_orders():
    return con.execute("""
        SELECT order_id, product_id, store_id, quantity, price, timestamp
        FROM streaming_orders
        ORDER BY timestamp DESC
        LIMIT 10
    """).fetchdf()

def get_ml_alerts():
    return con.execute("""
        SELECT product_id, store_id, risk_level, confidence, recommended_reorder
        FROM ml_alerts
        ORDER BY timestamp DESC
        LIMIT 5
    """).fetchdf()

# Layout
total_orders, revenue = get_live_metrics()

m_col1, m_col2 = st.columns(2)
with m_col1:
    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Total Orders Processed</div>
            <div class="metric-value">{total_orders:,}</div>
        </div>
    """, unsafe_allow_html=True)

with m_col2:
    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Revenue Generated Today</div>
            <div class="metric-value">₹ {revenue:,.2f}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-header">📦 Recent Transaction Stream</div>', unsafe_allow_html=True)
# Styling the dataframe is limited in Streamlit, but we can make it look decent
orders_df = get_recent_orders()
st.dataframe(orders_df, use_container_width=True, hide_index=True)

st.markdown('<div class="section-header">🚨 Intelligent Stockout Alerts (ML-Powered)</div>', unsafe_allow_html=True)

alerts = get_ml_alerts()

if alerts.empty:
    st.info("System healthy. No critical stockout risks detected in current stream.")
else:
    for _, row in alerts.iterrows():
        risk_class = row['risk_level'].lower()
        st.markdown(f"""
            <div class="alert-card alert-{risk_class}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <strong style="font-size: 1.1rem;">{row['product_id']}</strong> at <strong>{row['store_id']}</strong>
                        <div style="color: #666; font-size: 0.9rem;">Recommendation: Reorder <strong>{row['recommended_reorder']} units</strong> ASAP</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="background: {'#d32f2f' if row['risk_level'] == 'Critical' else '#ef6c00'}; color: white; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 700;">{row['risk_level']}</span>
                        <div style="font-size: 0.85rem; margin-top: 5px; color: #30364F;">ML Confidence: {row['confidence']}%</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# Auto-refresh
time.sleep(2)
st.rerun()
