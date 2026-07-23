"""
Populate fact_inventory from data/raw/inventory.csv.

inventory.csv has a known header/data mismatch: the header row reads
(date, store_id, product_id, stock_level) but the actual values in each
row are ordered (store_id, product_id, date, stock_level). This loader
reads the raw columns positionally and relabels them before mapping to
surrogate keys.

Run: python -m src.storage.populate_inventory
"""

import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = "data/warehouse/retail.duckdb"
CSV_PATH = "data/raw/inventory.csv"


def populate_inventory(con: duckdb.DuckDBPyConnection) -> int:
    print("\n--- fact_inventory ---")

    csv_path = Path(CSV_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"Required file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Header does not match data order; relabel positionally.
    df.columns = ["actual_store_id", "actual_product_id", "actual_date", "stock_level"]

    df["date_key"] = pd.to_datetime(df["actual_date"]).dt.strftime("%Y%m%d").astype(int)

    product_map = con.execute("SELECT product_id, product_key FROM dim_product").fetchdf()
    product_dict = dict(zip(product_map["product_id"], product_map["product_key"]))
    df["product_key"] = df["actual_product_id"].map(product_dict)

    store_map = con.execute("SELECT store_id, store_key FROM dim_store").fetchdf()
    store_dict = dict(zip(store_map["store_id"], store_map["store_key"]))
    df["store_key"] = df["actual_store_id"].map(store_dict)

    initial_rows = len(df)
    df = df.dropna(subset=["product_key", "store_key"])
    if len(df) < initial_rows:
        print(f"  Dropped {initial_rows - len(df)} rows due to unresolved product/store keys.")

    # reorder_point is not present in the source data; use a fixed baseline.
    df["reorder_point"] = 20

    con.register("temp_inventory", df)
    con.execute("DELETE FROM fact_inventory")
    con.execute(
        """
        INSERT INTO fact_inventory (date_key, product_key, store_key, stock_level, reorder_point)
        SELECT date_key, product_key, store_key, stock_level, reorder_point
        FROM temp_inventory
        """
    )
    con.unregister("temp_inventory")

    rows = con.execute("SELECT COUNT(*) FROM fact_inventory").fetchone()[0]
    print(f"  Rows: {rows:,}")
    if rows == 0:
        print("  WARNING: 0 rows in fact_inventory. Check inventory.csv and dim_product/dim_store keys.")
    return rows


if __name__ == "__main__":
    con = duckdb.connect(DB_PATH)
    try:
        populate_inventory(con)
    finally:
        con.close()
