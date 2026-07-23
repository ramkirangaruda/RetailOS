"""
Star schema build: deterministic, idempotent full rebuild of the retail warehouse.

Drops and recreates all dimension and fact tables, then loads from:
- data/raw/customers.csv      → dim_customer
- data/raw/products.csv      → dim_product
- data/raw/stores.csv        → dim_store
- generate_series 2024        → dim_date
- data/raw/transactions_cleaned.parquet → fact_sales (with FK joins)
- data/raw/inventory.csv      → fact_inventory (via populate_inventory)
- data/raw/shipments.csv      → fact_shipments (via populate_shipments)

Run: python -m src.transformation.build_schema
"""

import sys
import duckdb
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.storage.populate_inventory import populate_inventory
from src.storage.populate_shipments import populate_shipments

DB_PATH = Path("data/warehouse/retail.duckdb")
RAW_DIR = Path("data/raw")
CUSTOMERS_CSV = RAW_DIR / "customers.csv"
PRODUCTS_CSV = RAW_DIR / "products.csv"
STORES_CSV = RAW_DIR / "stores.csv"
TRANSACTIONS_CLEANED = RAW_DIR / "transactions_cleaned.parquet"


def _ensure_raw_paths() -> None:
    """Defensive check: ensure raw data paths exist."""
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Raw data directory not found: {RAW_DIR}")
    for name, p in [
        ("customers", CUSTOMERS_CSV),
        ("products", PRODUCTS_CSV),
        ("stores", STORES_CSV),
    ]:
        if not p.exists():
            raise FileNotFoundError(f"Required file not found: {p} (run data generator or add {name}.csv)")
    if not TRANSACTIONS_CLEANED.exists():
        raise FileNotFoundError(
            f"Cleaned transactions not found: {TRANSACTIONS_CLEANED}. Run data_cleaning.py first."
        )


def _drop_all_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Drop fact and dimension tables in dependency order."""
    print("\n--- Dropping existing tables ---")
    for table in [
        "fact_sales",
        "fact_inventory",
        "fact_shipments",
        "dim_date",
        "dim_customer",
        "dim_product",
        "dim_store",
        "dim_external_events",
    ]:
        con.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"  Dropped {table}")


def _create_dim_date(con: duckdb.DuckDBPyConnection) -> None:
    """Create dim_date and fill with full 2024 calendar."""
    print("\n--- dim_date ---")
    con.execute("""
        CREATE TABLE dim_date (
            date_key INTEGER,
            date DATE,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            is_weekend BOOLEAN,
            is_holiday BOOLEAN,
            festival_name VARCHAR
        )
    """)
    con.execute("""
        INSERT INTO dim_date (
            date_key, date, year, month, day, is_weekend, is_holiday, festival_name
        )
        SELECT
            CAST(strftime('%Y%m%d', d) AS INTEGER),
            d,
            EXTRACT(year FROM d),
            EXTRACT(month FROM d),
            EXTRACT(day FROM d),
            EXTRACT(dow FROM d) IN (0, 6),
            FALSE,
            NULL
        FROM generate_series(
            '2024-01-01'::DATE,
            '2024-12-31'::DATE,
            INTERVAL 1 DAY
        ) AS t(d)
    """)
    n = con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
    print(f"  Rows: {n}")


def _create_dim_customer(con: duckdb.DuckDBPyConnection) -> None:
    """Create dim_customer matching customers.csv and load from CSV."""
    print("\n--- dim_customer ---")
    con.execute("""
        CREATE TABLE dim_customer (
            customer_key BIGINT,
            customer_id VARCHAR,
            name VARCHAR,
            email VARCHAR,
            phone VARCHAR,
            city VARCHAR,
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            is_current BOOLEAN,
            version INTEGER
        )
    """)
    csv_path = str(CUSTOMERS_CSV.resolve())
    con.execute(f"""
        INSERT INTO dim_customer (
            customer_key, customer_id, name, email, phone, city,
            valid_from, valid_to, is_current, version
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY customer_id) AS customer_key,
            customer_id,
            name,
            email,
            phone,
            city,
            CURRENT_TIMESTAMP AS valid_from,
            NULL AS valid_to,
            TRUE AS is_current,
            1 AS version
        FROM read_csv_auto('{csv_path}')
    """)
    n = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    print(f"  Rows: {n}")
    if n == 0:
        print("  WARNING: 0 rows in dim_customer. Check customers.csv and column names.")


def _create_dim_product(con: duckdb.DuckDBPyConnection) -> None:
    """Create dim_product with 6 columns; load from products.csv (product_name→name, base_price→price, brand=NULL)."""
    print("\n--- dim_product ---")
    con.execute("""
        CREATE TABLE dim_product (
            product_key INTEGER,
            product_id VARCHAR,
            name VARCHAR,
            category VARCHAR,
            brand VARCHAR,
            price DOUBLE
        )
    """)
    csv_path = str(PRODUCTS_CSV.resolve())
    con.execute(f"""
        INSERT INTO dim_product (
            product_key, product_id, name, category, brand, price
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY product_id)::INTEGER AS product_key,
            product_id,
            product_name AS name,
            category,
            CAST(NULL AS VARCHAR) AS brand,
            base_price AS price
        FROM read_csv_auto('{csv_path}')
    """)
    n = con.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0]
    print(f"  Rows: {n}")
    if n == 0:
        print("  WARNING: 0 rows in dim_product. Check products.csv has product_id, product_name, category, base_price.")


def _create_dim_store(con: duckdb.DuckDBPyConnection) -> None:
    """Create dim_store with region derived from city (North/South/East/West)."""
    print("\n--- dim_store ---")
    con.execute("""
        CREATE TABLE dim_store (
            store_key BIGINT,
            store_id VARCHAR,
            store_name VARCHAR,
            city VARCHAR,
            region VARCHAR
        )
    """)
    csv_path = str(STORES_CSV.resolve())
    con.execute(f"""
        INSERT INTO dim_store (store_key, store_id, store_name, city, region)
        SELECT
            ROW_NUMBER() OVER (ORDER BY store_id) AS store_key,
            store_id,
            store_name,
            city,
            CASE
                WHEN UPPER(TRIM(city)) IN ('MUMBAI', 'PUNE', 'AHMEDABAD', 'SURAT') THEN 'West'
                WHEN UPPER(TRIM(city)) IN ('DELHI', 'JAIPUR') THEN 'North'
                WHEN UPPER(TRIM(city)) IN ('BANGALORE', 'CHENNAI', 'HYDERABAD') THEN 'South'
                WHEN UPPER(TRIM(city)) = 'KOLKATA' THEN 'East'
                ELSE 'Unknown'
            END AS region
        FROM read_csv_auto('{csv_path}')
    """)
    n = con.execute("SELECT COUNT(*) FROM dim_store").fetchone()[0]
    print(f"  Rows: {n}")
    if n == 0:
        print("  WARNING: 0 rows in dim_store. Check stores.csv.")


def _create_fact_sales(con: duckdb.DuckDBPyConnection) -> None:
    """Create fact_sales and load from transactions_cleaned.parquet with FK joins. Only insert where all FKs resolve."""
    print("\n--- fact_sales ---")
    con.execute("""
        CREATE TABLE fact_sales (
            sale_id VARCHAR,
            date_key INTEGER,
            customer_key BIGINT,
            product_key BIGINT,
            store_key BIGINT,
            quantity INTEGER,
            revenue DOUBLE,
            discount DOUBLE
        )
    """)

    parquet_path = str(TRANSACTIONS_CLEANED.resolve())
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _stg_trans AS
        SELECT * FROM read_parquet('{parquet_path}')
    """)

    # Join to dims; only rows where all FKs are NOT NULL (inner join)
    # Use transaction date column: 'date' in parquet (not transaction_date)
    con.execute("""
        INSERT INTO fact_sales (
            sale_id, date_key, customer_key, product_key, store_key,
            quantity, revenue, discount
        )
        SELECT
            t.transaction_id AS sale_id,
            dd.date_key,
            dc.customer_key,
            dp.product_key,
            ds.store_key,
            t.quantity,
            (t.quantity * t.price - COALESCE(t.discount, 0)) AS revenue,
            COALESCE(t.discount, 0) AS discount
        FROM _stg_trans t
        INNER JOIN dim_customer dc
            ON dc.customer_id = t.customer_id AND dc.is_current = TRUE
        INNER JOIN dim_product dp ON dp.product_id = t.product_id
        INNER JOIN dim_store ds ON ds.store_id = t.store_id
        INNER JOIN dim_date dd ON dd.date = CAST(t.date AS DATE)
        WHERE t.customer_id IS NOT NULL
          AND t.product_id IS NOT NULL
          AND t.store_id IS NOT NULL
          AND t.date IS NOT NULL
    """)

    n = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    print(f"  Rows: {n}")
    if n == 0:
        print("  WARNING: 0 rows in fact_sales. Check:")
        print("    - transactions_cleaned.parquet has date, customer_id, product_id, store_id")
        print("    - dim_customer has matching customer_id (is_current=TRUE)")
        print("    - dim_product has matching product_id")
        print("    - dim_store has matching store_id")
        print("    - dim_date has dates covering transaction dates (2024)")


def _create_placeholder_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create fact_inventory / fact_shipments schemas (populated separately) and
    dim_external_events (genuinely unused, kept empty to avoid schema drift)."""
    print("\n--- dim_external_events, fact_inventory, fact_shipments (schema only) ---")
    con.execute("""
        CREATE TABLE dim_external_events (
            event_id BIGINT,
            event_name VARCHAR,
            event_date DATE,
            region VARCHAR,
            demand_impact DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE fact_inventory (
            inventory_id BIGINT,
            date_key INTEGER,
            product_key BIGINT,
            store_key BIGINT,
            stock_level INTEGER,
            reorder_point INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE fact_shipments (
            shipment_id VARCHAR,
            date_key INTEGER,
            product_key BIGINT,
            store_key BIGINT,
            delivery_time DOUBLE,
            on_time_flag BOOLEAN
        )
    """)
    print("  Tables created.")


def _load_inventory_and_shipments(con: duckdb.DuckDBPyConnection) -> None:
    """Populate fact_inventory and fact_shipments now that fact_sales/dims exist."""
    populate_inventory(con)
    populate_shipments(con)


def build_star_schema() -> None:
    """Full deterministic rebuild: drop all, create all, load from CSV/parquet."""
    print("=" * 60)
    print("STAR SCHEMA BUILD (deterministic, idempotent)")
    print("=" * 60)

    _ensure_raw_paths()
    db_path_str = str(DB_PATH.resolve())

    con = duckdb.connect(db_path_str)
    try:
        _drop_all_tables(con)
        _create_dim_date(con)
        _create_dim_customer(con)
        _create_dim_product(con)
        _create_dim_store(con)
        _create_fact_sales(con)
        _create_placeholder_tables(con)
        _load_inventory_and_shipments(con)

        print("\n--- Final row counts ---")
        for table in ["dim_product", "dim_customer", "dim_store", "dim_date", "fact_sales", "fact_inventory", "fact_shipments"]:
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {n:,}")
        print("\nStar schema build complete.")
    finally:
        con.close()
        print("Connection closed.")


if __name__ == "__main__":
    build_star_schema()
