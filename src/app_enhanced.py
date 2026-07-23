import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import asyncio
import json
import pandas as pd
import time
import sys
import os
from pathlib import Path

# Add parent directory to path to allow importing config
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
try:
    from config import DB_PATH
except ImportError:
    DB_PATH = 'data/warehouse/retail.duckdb'

st.set_page_config(page_title="RetailOS Intelligence Platform", layout="wide", page_icon="🏪")

@st.cache_resource
def get_db_connection():
    try:
        return duckdb.connect(str(DB_PATH), read_only=True)
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return None

con = get_db_connection()

# Initialize session state for auto-refresh
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

st.title("🏪 RetailOS Intelligence Platform")

# Sidebar
with st.sidebar:
    st.header("System Status")
    
    if con:
        # Pipeline status
        try:
            last_run = con.execute("""
            SELECT start_time, status, rows_processed, duration_seconds
            FROM pipeline_runs
            ORDER BY run_id DESC
            LIMIT 1
            """).fetchdf()
            
            if not last_run.empty:
                status_emoji = "✅" if last_run.iloc[0]['status'] == 'success' else "❌"
                st.metric(
                    "Last Pipeline Run",
                    last_run.iloc[0]['start_time'].strftime('%H:%M'),
                    f"{status_emoji} {last_run.iloc[0]['rows_processed']:,} rows"
                )
            else:
                st.info("No pipeline runs recorded yet.")
        except Exception:
            st.warning("Pipeline run table not found.")
    else:
        st.error("Database disconnected")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-Refresh Data (5s)", value=False)
    
    # Model status
    st.subheader("ML Models")
    models = ['Stockout Classifier', 'Reorder Regressor']
    for model in models:
        st.write(f"✅ {model}")

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Live Intelligence", 
    "🤖 ML Reasoning", 
    "✅ Schema Evolution", 
    "📈 Pipeline Monitoring",
    "⚠️ Approval Queue"
])

if not con:
    st.stop()

## TAB 1: LIVE INTELLIGENCE
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        # Check if streaming_orders exists
        con.execute("SELECT 1 FROM streaming_orders LIMIT 1")
        
        # Real-time metrics
        today_stats = con.execute("""
        SELECT 
            COUNT(*) as orders_today,
            COALESCE(SUM(price * quantity), 0) as revenue_today,
            COALESCE(AVG(price * quantity), 0) as avg_order_value,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM streaming_orders
        WHERE DATE(timestamp) = CURRENT_DATE
        """).fetchdf().iloc[0]
        
        col1.metric("Orders Today", f"{today_stats['orders_today']:,}")
        col2.metric("Revenue Today", f"₹{today_stats['revenue_today']:,.0f}")
        col3.metric("Avg Order Value", f"₹{today_stats['avg_order_value']:,.0f}")
        col4.metric("Unique Customers", f"{today_stats['unique_customers']:,}")
        
    except Exception:
        st.warning("Streaming orders table not found. Start the WebSocket generator first.")
        col1.metric("Orders Today", "0")

    # Stockout risks with ML predictions
    st.subheader("🚨 ML-Predicted Stockout Risks")

    try:
        latest = con.execute("""
        SELECT
            ml.store_id,
            ml.product_id,
            dp.name as product_name,
            ds.store_name,
            ml.prediction as recommended_reorder,
            ml.confidence,
            ml.explanation_json
        FROM ml_reasoning_log ml
        JOIN dim_product dp ON ml.product_id = dp.product_id
        JOIN dim_store ds ON ml.store_id = ds.store_id
        WHERE ml.timestamp = (
            SELECT MAX(timestamp) FROM ml_reasoning_log ml2
            WHERE ml2.store_id = ml.store_id AND ml2.product_id = ml.product_id
        )
        """).fetchdf()

        def _parse_explanation(raw):
            try:
                return json.loads(raw) if raw else {}
            except (TypeError, json.JSONDecodeError):
                return {}

        latest["explanation"] = latest["explanation_json"].apply(_parse_explanation)
        latest["risk_level"] = latest["explanation"].apply(lambda e: e.get("risk_level", "Unknown"))
        latest["current_stock"] = latest["explanation"].apply(lambda e: e.get("current_stock", 0))
        latest["avg_daily_demand"] = latest["explanation"].apply(lambda e: e.get("avg_daily_demand", 0))
        # Simple stock-runway estimate (current_stock / avg_daily_demand), NOT a
        # forecast model — no Prophet or other time-series forecasting is
        # implemented anywhere in this codebase.
        latest["days_remaining"] = latest.apply(
            lambda r: round(r["current_stock"] / r["avg_daily_demand"], 1) if r["avg_daily_demand"] else None,
            axis=1,
        )

        risks = latest[latest["risk_level"].isin(["High", "Critical"])].sort_values(
            "days_remaining", na_position="last"
        ).head(20)

        if not risks.empty:
            for _, row in risks.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
                    c1.write(f"**{row['store_name']}**")
                    c2.write(row['product_name'])
                    c3.metric("Stock", f"{row['current_stock']:.0f}")
                    days_label = f"{row['days_remaining']:.1f}" if row['days_remaining'] is not None else "N/A"
                    c4.metric("Days Remaining", days_label,
                               delta=f"{row['confidence']:.0%} conf", delta_color="inverse")
                    c5.button("Reorder", key=f"ro_{row['store_id']}_{row['product_id']}")
        else:
            st.success("✅ No high-risk stockouts predicted")
    except Exception as e:
        st.info(f"ML predictions not available: {e}")
    
    # Live order feed
    st.subheader("🔴 Recent Orders")
    try:
        recent = con.execute("""
        SELECT order_id, timestamp, product_id, quantity, price, payment_method, order_source 
        FROM streaming_orders 
        ORDER BY timestamp DESC 
        LIMIT 10
        """).fetchdf()
        st.dataframe(recent, use_container_width=True, hide_index=True)
    except:
        pass

## TAB 2: ML REASONING EXPLORER
with tab2:
    st.header("🤖 ML Model Reasoning Explorer")

    try:
        # Select a recent prediction
        recent_predictions = con.execute("""
        SELECT id, timestamp, store_id, product_id, prediction, confidence, explanation_json
        FROM ml_reasoning_log
        ORDER BY timestamp DESC
        LIMIT 50
        """).fetchdf()

        if not recent_predictions.empty:
            def _risk_level(raw):
                try:
                    return json.loads(raw).get("risk_level", "Unknown") if raw else "Unknown"
                except (TypeError, json.JSONDecodeError):
                    return "Unknown"

            recent_predictions["risk_level"] = recent_predictions["explanation_json"].apply(_risk_level)

            options = recent_predictions["id"].tolist()
            labels = {
                row["id"]: f"{row['timestamp']} | Store {row['store_id']} | Product {row['product_id']} | Risk: {row['risk_level']}"
                for _, row in recent_predictions.iterrows()
            }
            selected_id = st.selectbox(
                "Select a prediction to examine:",
                options,
                format_func=lambda i: labels[i],
            )

            row = recent_predictions[recent_predictions["id"] == selected_id].iloc[0]
            try:
                explanation = json.loads(row["explanation_json"]) if row["explanation_json"] else {}
            except (TypeError, json.JSONDecodeError):
                explanation = {}

            # Display reasoning
            c1, c2, c3 = st.columns(3)
            c1.metric("ML Confidence", f"{row['confidence']:.1%}")
            c2.metric("Risk Level", explanation.get("risk_level", "Unknown"))
            c3.metric("Recommended Reorder", f"{row['prediction']:.0f} units")

            st.subheader("📊 Prediction Factors")

            # Create factor visualization. No Prophet or other time-series
            # forecasting is implemented anywhere in this codebase, so only
            # the features the classifier/regressor actually saw are shown.
            factors = {
                'Current Stock': explanation.get('current_stock', 0),
                'Avg Daily Demand': explanation.get('avg_daily_demand', 0),
                'Demand Volatility (CV)': explanation.get('volatility_cv', 0),
            }

            fig = go.Figure(data=[
                go.Bar(x=list(factors.keys()), y=list(factors.values()))
            ])
            fig.update_layout(title="Key Factors in Prediction", height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No ML predictions found in log.")
    except Exception as e:
        st.error(f"Error loading ML reasoning: {e}")

## TAB 3: SCHEMA EVOLUTION DASHBOARD
with tab3:
    st.header("🔄 Adaptive Schema Evolution")
    
    try:
        # Summary stats
        c1, c2, c3 = st.columns(3)
        
        total_changes = con.execute("SELECT COUNT(*) FROM schema_change_log").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM schema_change_log WHERE status = 'pending'").fetchone()[0]
        auto_approved = con.execute("SELECT COUNT(*) FROM schema_change_log WHERE status = 'auto_approved'").fetchone()[0]
        
        c1.metric("Total Schema Changes", total_changes)
        c2.metric("Pending Approval", pending)
        c3.metric("Auto-Approved", auto_approved)
        
        # Recent changes
        st.subheader("Recent Schema Changes")
        
        changes = con.execute("""
        SELECT 
            detected_at,
            table_name,
            change_type,
            column_name,
            confidence_score,
            status
        FROM schema_change_log
        ORDER BY detected_at DESC
        LIMIT 20
        """).fetchdf()
        
        st.dataframe(changes, use_container_width=True)
        
    except Exception as e:
        st.error(f"Schema logs not available or empty: {e}")

## TAB 4: PIPELINE MONITORING
with tab4:
    st.header("📈 Pipeline Performance Monitoring")
    
    try:
        # Run history
        runs = con.execute("""
        SELECT 
            start_time,
            status,
            rows_processed,
            rows_quarantined,
            duration_seconds
        FROM pipeline_runs
        ORDER BY run_id DESC
        LIMIT 50
        """).fetchdf()
        
        if not runs.empty:
            # Success rate
            success_rate = (runs['status'] == 'success').sum() / len(runs) * 100
            st.metric("Pipeline Success Rate", f"{success_rate:.1f}%")
            
            # Performance over time
            fig = px.line(runs, x='start_time', y='duration_seconds', 
                         title="Pipeline Duration Over Time")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No pipeline runs to display.")
            
    except Exception as e:
        st.error(f"Monitoring data not available: {e}")

## TAB 5: APPROVAL QUEUE
with tab5:
    st.header("⚠️ Order/Schema Approval Queue")
    # Placeholder for approval queue logic
    st.info("Approval queue is currently empty.")

# Auto-refresh handling
if auto_refresh:
    time.sleep(5)
    st.rerun()