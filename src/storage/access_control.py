#!/usr/bin/env python3
"""
RBAC and PII Masking Implementation for RetailOS.

Creates secure DuckDB views (analyst_sales, store_manager_sales,
finance_sales, admin_all) that mask customer PII and restrict financial
detail depending on role.

verify_schema(con) and create_rbac_views(con) are library functions that
take an existing connection and raise a plain exception on failure -
they're safe to call from the API's startup path (see src/api/server.py)
without killing the whole process. Running this file directly still gives
the original CLI behavior: connect, verify, create views, print samples,
and exit(1) on failure, for standalone/manual use.

IMPORTANT SCOPE NOTE: these views only govern access for callers that go
through the FastAPI layer (src/api/server.py), which is the only place
this project enforces role checks (see src/api/auth.py). Anyone who opens
data/warehouse/retail.duckdb directly - e.g. a BI tool, notebook, or copy
of the file - bypasses these views entirely and can query fact_sales /
dim_customer unmasked. DuckDB is an embedded, single-file database with no
native per-user GRANT/REVOKE system, so enforcing this at the file level
isn't possible without moving to a client-server database; the mitigation
here is applicaton-layer access control plus keeping the .duckdb file off
of anything but the API/dashboard processes (documented in docs/STORAGE.md).
"""

import duckdb
import sys

DB_PATH = "data/warehouse/retail.duckdb"


def verify_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Verify the database schema before creating views. Raises RuntimeError on failure."""
    tables = con.execute("SHOW TABLES").fetchdf()
    required_tables = ['fact_sales', 'dim_customer', 'dim_product', 'dim_store', 'dim_date']
    for table in required_tables:
        if table not in tables['name'].values:
            raise RuntimeError(f"Required table {table} not found in database")

    fact_sales_columns = con.execute("DESCRIBE fact_sales").fetchdf()
    required_fact_columns = ['sale_id', 'date_key', 'customer_key', 'product_key', 'store_key', 'quantity', 'revenue']
    for col in required_fact_columns:
        if col not in fact_sales_columns['column_name'].values:
            raise RuntimeError(f"Required column {col} not found in fact_sales")

    customer_columns = con.execute("DESCRIBE dim_customer").fetchdf()
    required_customer_columns = ['customer_key', 'name', 'email', 'phone', 'city']
    for col in required_customer_columns:
        if col not in customer_columns['column_name'].values:
            raise RuntimeError(f"Required column {col} not found in dim_customer")

    product_columns = con.execute("DESCRIBE dim_product").fetchdf()
    required_product_columns = ['product_key', 'name', 'category', 'price']
    for col in required_product_columns:
        if col not in product_columns['column_name'].values:
            raise RuntimeError(f"Required column {col} not found in dim_product")


def create_rbac_views(con: duckdb.DuckDBPyConnection) -> None:
    """Create/replace RBAC views with PII masking. Raises on failure."""
    con.execute("DROP VIEW IF EXISTS analyst_sales")
    con.execute("DROP VIEW IF EXISTS store_manager_sales")
    con.execute("DROP VIEW IF EXISTS finance_sales")
    con.execute("DROP VIEW IF EXISTS admin_all")

    con.execute("""
        CREATE VIEW analyst_sales AS
        SELECT
            fs.sale_id, fs.date_key, fs.product_key, fs.store_key,
            fs.quantity, fs.revenue,
            CONCAT('XXXXX-', RIGHT(dc.phone, 4)) as phone_masked,
            CONCAT(LEFT(dc.email, 1), '***@', SPLIT_PART(dc.email, '@', 2)) as email_masked,
            dc.city as customer_city
        FROM fact_sales fs
        JOIN dim_customer dc ON fs.customer_key = dc.customer_key
    """)

    con.execute("""
        CREATE VIEW store_manager_sales AS
        SELECT * FROM analyst_sales
    """)

    con.execute("""
        CREATE VIEW finance_sales AS
        SELECT
            fs.*,
            dc.name as customer_name,
            dc.email,
            dc.phone,
            dc.city as customer_city,
            dp.name as product_name,
            dp.category as product_category,
            dp.price as product_price,
            (fs.revenue - (dp.price * fs.quantity)) as profit
        FROM fact_sales fs
        JOIN dim_customer dc ON fs.customer_key = dc.customer_key
        JOIN dim_product dp ON fs.product_key = dp.product_key
    """)

    con.execute("""
        CREATE VIEW admin_all AS
        SELECT
            'fact_sales' as table_name, COUNT(*) as row_count,
            MIN(date_key) as min_date_key, MAX(date_key) as max_date_key,
            SUM(revenue) as total_revenue
        FROM fact_sales
        UNION ALL
        SELECT 'dim_customer', COUNT(*), NULL, NULL, NULL FROM dim_customer
        UNION ALL
        SELECT 'dim_product', COUNT(*), NULL, NULL, NULL FROM dim_product
        UNION ALL
        SELECT 'dim_store', COUNT(*), NULL, NULL, NULL FROM dim_store
        UNION ALL
        SELECT 'dim_date', COUNT(*), MIN(date_key), MAX(date_key), NULL FROM dim_date
    """)


def _run_cli() -> None:
    print("🚀 RetailOS RBAC and PII Masking Implementation")
    print("=" * 50)

    con = duckdb.connect(DB_PATH)
    try:
        print("\n🔗 Verifying schema...")
        verify_schema(con)
        print("✓ Schema verification passed")

        print("\n🗑️  Creating RBAC views...")
        create_rbac_views(con)
        print("✓ Created: analyst_sales, store_manager_sales, finance_sales, admin_all")

        analyst_count = con.execute("SELECT COUNT(*) FROM analyst_sales").fetchone()[0]
        finance_count = con.execute("SELECT COUNT(*) FROM finance_sales").fetchone()[0]
        print(f"✓ analyst_sales: {analyst_count:,} rows")
        print(f"✓ finance_sales: {finance_count:,} rows")

        print("\n🔍 Sample data verification:")
        print("\n--- analyst_sales sample (PII masked) ---")
        print(con.execute(
            "SELECT sale_id, phone_masked, email_masked, customer_city, revenue FROM analyst_sales LIMIT 3"
        ).fetchdf().to_string(index=False))

        print("\n--- finance_sales sample (full access) ---")
        print(con.execute(
            "SELECT sale_id, customer_name, email, phone, profit FROM finance_sales LIMIT 3"
        ).fetchdf().to_string(index=False))

        print("\n--- admin_all sample ---")
        print(con.execute("SELECT * FROM admin_all").fetchdf().to_string(index=False))

        print("\n✅ RBAC views created successfully!")
        print("🔐 Database views are ready for role-based, PII-masked access.")
        print("\n📋 Usage Examples:")
        print("  SELECT * FROM analyst_sales WHERE revenue > 1000;")
        print("  SELECT * FROM store_manager_sales WHERE store_key = 5;")
        print("  SELECT customer_name, profit FROM finance_sales WHERE profit > 0;")
        print("  SELECT * FROM admin_all;")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        con.close()


if __name__ == "__main__":
    _run_cli()
