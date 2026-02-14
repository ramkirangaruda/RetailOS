import streamlit as st
import duckdb
import pandas as pd
from src.intelligence.ml_predictive_engine import MLPredictiveEngine

DB_PATH = "data/warehouse/retail.duckdb"

st.set_page_config(page_title="RetailOS ML Dashboard", layout="wide")
st.title("🤖 RetailOS ML Control Center")

# ===============================
# SINGLE SHARED DB CONNECTION
# ===============================
@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH)

con = get_connection()

# Attach ML engine to SAME connection
engine = MLPredictiveEngine(con)

# ===============================
# LIVE ALERTS
# ===============================
st.subheader("🚨 Recent ML Alerts")

alerts = con.execute("""
    SELECT *
    FROM ml_alerts
    ORDER BY timestamp DESC
    LIMIT 10
""").fetchdf()

if alerts.empty:
    st.success("No active stockout alerts.")
else:
    st.dataframe(alerts, use_container_width=True)

st.divider()

# ===============================
# AUTO REORDERS
# ===============================
st.subheader("📦 Auto Reorders Generated")

reorders = con.execute("""
    SELECT *
    FROM auto_reorders
    ORDER BY timestamp DESC
    LIMIT 10
""").fetchdf()

if reorders.empty:
    st.info("No auto reorders triggered yet.")
else:
    st.dataframe(reorders, use_container_width=True)

st.divider()

# ===============================
# MANUAL ML TEST
# ===============================
st.subheader("🧪 Test ML Prediction")

product_id = st.text_input("Product ID (e.g., P0001)")
store_id = st.text_input("Store ID (e.g., ST001)")

if st.button("Run ML Prediction"):

    if product_id and store_id:

        result = engine.predict_stockout_with_explanation(
            product_id,
            store_id
        )

        if result is None:
            st.warning("No inventory record found.")
        else:
            st.write("### Prediction Result")
            st.json(result)

    else:
        st.warning("Enter both Product ID and Store ID.")
