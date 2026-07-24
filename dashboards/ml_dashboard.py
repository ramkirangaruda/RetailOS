import sys
import os
import pandas as pd
import streamlit as st

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.intelligence.ml_predictive_engine import MLPredictiveEngine


st.set_page_config(page_title="ML Stockout Prediction Engine", layout="wide")

st.title("📦 ML Stockout Prediction Engine")

engine = MLPredictiveEngine()

# =====================================================
# SINGLE PRODUCT PREDICTION
# =====================================================

st.subheader("🔍 Predict Specific Product")

product_id = st.text_input("Enter Product ID", "P0011")
store_id = st.text_input("Enter Store ID", "ST033")

if st.button("Predict Stockout Risk"):

    result = engine.predict_stockout_with_explanation(product_id, store_id)

    if result is None:
        st.error("No data available for this product/store.")
    else:
        risk_label = result["explanation"]["risk_level"]
        confidence = result["confidence"] * 100
        reorder = result["recommended_reorder"]

        if risk_label == "Critical":
            st.error(f"🔴 Risk Level: {risk_label}")
        elif risk_label == "High":
            st.warning(f"🟠 Risk Level: {risk_label}")
        elif risk_label == "Medium":
            st.info(f"🟡 Risk Level: {risk_label}")
        else:
            st.success(f"🟢 Risk Level: {risk_label}")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Confidence", f"{confidence:.1f}%")

        with col2:
            st.metric("Recommended Reorder", f"{reorder} units")

        st.subheader("Explanation")
        explanation = result["explanation"]

        st.write(f"Current Stock: {explanation['current_stock']}")
        st.write(f"Avg Daily Demand: {explanation['avg_daily_demand']}")
        st.write(f"Volatility (CV): {explanation['volatility_cv']}")


# =====================================================
# SCAN ALL PRODUCTS
# =====================================================

st.divider()
st.subheader("🚨 Scan Entire Inventory for Risk")

if st.button("Scan All Products"):

    df = engine.con.execute("""
        SELECT DISTINCT dp.product_id, ds.store_id
        FROM fact_inventory fi
        JOIN dim_product dp ON fi.product_key = dp.product_key
        JOIN dim_store ds ON fi.store_key = ds.store_key
    """).fetchdf()

    results = []

    for _, row in df.iterrows():
        result = engine.predict_stockout_with_explanation(
            row["product_id"],
            row["store_id"]
        )

        if result:
            results.append({
                "Product": row["product_id"],
                "Store": row["store_id"],
                "Risk": result["explanation"]["risk_level"],
                "Confidence (%)": round(result["confidence"] * 100, 1),
                "Recommended Reorder": result["recommended_reorder"]
            })

    if results:
        risk_df = pd.DataFrame(results)

        # Show highest risk first
        risk_df = risk_df.sort_values(
            by=["Risk", "Confidence (%)"],
            ascending=[False, False]
        )

        st.dataframe(risk_df, use_container_width=True)
    else:
        st.info("No products found.")
