"""
Populate fact_shipments from data/raw/shipments.csv.

shipments.csv has no store_id/product_id of its own; each shipment is tied
to an order via transaction_id, which matches fact_sales.sale_id. We resolve
product_key/store_key through that join at load time, so downstream KPI
queries can aggregate fact_shipments directly without re-joining fact_sales.

delivery_time is derived as (delivery_date - ship_date) in days.
on_time_flag uses a fixed threshold of 5 days: the source data has no
explicit SLA, and 5 days is the median observed delivery_time in this
dataset, so it's used as a documented, reasonable on-time cutoff.

Run: python -m src.storage.populate_shipments
"""

import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = "data/warehouse/retail.duckdb"
CSV_PATH = "data/raw/shipments.csv"
ON_TIME_THRESHOLD_DAYS = 5


def populate_shipments(con: duckdb.DuckDBPyConnection) -> int:
    print("\n--- fact_shipments ---")

    csv_path = Path(CSV_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"Required file not found: {csv_path}")

    df = pd.read_csv(csv_path, parse_dates=["ship_date", "delivery_date"])
    df["delivery_time"] = (df["delivery_date"] - df["ship_date"]).dt.days
    df["on_time_flag"] = df["delivery_time"] <= ON_TIME_THRESHOLD_DAYS

    con.register("temp_shipments", df)

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _stg_shipments_resolved AS
        SELECT
            ts.shipment_id,
            dd.date_key,
            fs.product_key,
            fs.store_key,
            ts.delivery_time,
            ts.on_time_flag
        FROM temp_shipments ts
        JOIN fact_sales fs ON fs.sale_id = ts.transaction_id
        JOIN dim_date dd ON dd.date = CAST(ts.ship_date AS DATE)
        """
    )

    matched = con.execute("SELECT COUNT(*) FROM _stg_shipments_resolved").fetchone()[0]
    unmatched = len(df) - matched
    if unmatched > 0:
        print(f"  Dropped {unmatched} shipments with no matching fact_sales.sale_id (transaction not in fact_sales).")

    con.execute("DELETE FROM fact_shipments")
    con.execute(
        """
        INSERT INTO fact_shipments (shipment_id, date_key, product_key, store_key, delivery_time, on_time_flag)
        SELECT shipment_id, date_key, product_key, store_key, delivery_time, on_time_flag
        FROM _stg_shipments_resolved
        """
    )
    con.unregister("temp_shipments")

    rows = con.execute("SELECT COUNT(*) FROM fact_shipments").fetchone()[0]
    print(f"  Rows: {rows:,}")
    if rows == 0:
        print("  WARNING: 0 rows in fact_shipments. Check shipments.csv and fact_sales.sale_id linkage.")
    return rows


if __name__ == "__main__":
    con = duckdb.connect(DB_PATH)
    try:
        populate_shipments(con)
    finally:
        con.close()
