import streamlit as st
import importlib

st.set_page_config(
    page_title="RetailOS Live Command Center",
    layout="wide"
)

st.title("🚀 RetailOS Live Command Center")

dashboard = st.sidebar.radio(
    "Choose Module",
    [
        "Live Streaming",
        "ML Dashboard",
        "Schema Monitor"
    ]
)

if dashboard == "Live Streaming":
    module = importlib.import_module("dashboards.live_stream_dashboard")
    importlib.reload(module)

elif dashboard == "ML Dashboard":
    module = importlib.import_module("dashboards.ml_dashboard")
    importlib.reload(module)

elif dashboard == "Schema Monitor":
    module = importlib.import_module("dashboards.schema_dashboard")
    importlib.reload(module)
