"""
Export a small, committable sample of the final star-schema tables as CSV,
for the "Analytical Dataset" deliverable - a preview of the cleaned,
structured data without committing the full generated warehouse (which
stays gitignored; regenerate it locally via data_generator.py +
build_schema.py).

dim_customer's phone/email are masked using the same logic as
src/storage/access_control.py's analyst_sales view, since this file is
meant to be committed to the repo (public within it) rather than served
behind the API's role-gated endpoints.

Run: python -m src.storage.export_sample_dataset
"""

import duckdb
from pathlib import Path

DB_PATH = "data/warehouse/retail.duckdb"
OUTPUT_DIR = Path("docs/sample_dataset")
SAMPLE_ROWS = 200


def export_sample_dataset() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=True)

    try:
        _export(con, "dim_customer_sample", f"""
            SELECT
                customer_key, customer_id, name, city,
                CONCAT('XXXXX-', RIGHT(phone, 4)) as phone_masked,
                CONCAT(LEFT(email, 1), '***@', SPLIT_PART(email, '@', 2)) as email_masked,
                valid_from, valid_to, is_current, version
            FROM dim_customer
            ORDER BY customer_key
            LIMIT {SAMPLE_ROWS}
        """)

        _export(con, "dim_product_sample", f"""
            SELECT * FROM dim_product ORDER BY product_key LIMIT {SAMPLE_ROWS}
        """)

        _export(con, "dim_store_sample", "SELECT * FROM dim_store ORDER BY store_key")

        _export(con, "dim_date_sample", f"""
            SELECT * FROM dim_date ORDER BY date_key LIMIT {SAMPLE_ROWS}
        """)

        _export(con, "fact_sales_sample", f"""
            SELECT * FROM fact_sales ORDER BY date_key, sale_id LIMIT {SAMPLE_ROWS}
        """)

        _export(con, "fact_inventory_sample", f"""
            SELECT * FROM fact_inventory ORDER BY date_key, product_key, store_key LIMIT {SAMPLE_ROWS}
        """)

        _export(con, "fact_shipments_sample", f"""
            SELECT * FROM fact_shipments ORDER BY date_key, shipment_id LIMIT {SAMPLE_ROWS}
        """)

        print(f"\nSample dataset exported to {OUTPUT_DIR}/")
    finally:
        con.close()


def _export(con: duckdb.DuckDBPyConnection, name: str, query: str) -> None:
    df = con.execute(query).fetchdf()
    out_path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(out_path, index=False)
    print(f"  {name}: {len(df):,} rows -> {out_path}")


if __name__ == "__main__":
    export_sample_dataset()
