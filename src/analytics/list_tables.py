"""
Script to list all tables in the DuckDB warehouse.
Run: python src/analytics/list_tables.py
"""

import duckdb
from pathlib import Path

# Path to your DuckDB database
DB_PATH = "data/warehouse/retail.duckdb"

def list_all_tables():
    """List all tables in the DuckDB database"""
    
    # Step 1: Connect to DuckDB database
    print("=" * 60)
    print("Connecting to DuckDB database...")
    print(f"Database: {DB_PATH}")
    print("=" * 60)
    
    con = duckdb.connect(DB_PATH)
    
    try:
        # Step 2: Method 1 - Using SHOW TABLES (simplest)
        print("\n--- Method 1: SHOW TABLES ---")
        tables = con.execute("SHOW TABLES").fetchall()
        
        if tables:
            print(f"\nFound {len(tables)} table(s):\n")
            for i, (table_name,) in enumerate(tables, 1):
                print(f"  {i}. {table_name}")
        else:
            print("  No tables found.")
        
        # Step 3: Method 2 - Using information_schema (more detailed)
        print("\n--- Method 2: information_schema.tables (with details) ---")
        table_info = con.execute("""
            SELECT 
                table_name,
                table_type
            FROM information_schema.tables 
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchdf()
        
        if not table_info.empty:
            print(f"\nTable Details:\n")
            print(table_info.to_string(index=False))
        else:
            print("  No tables found.")
        
        # Step 4: Get row counts for each table
        print("\n--- Table Row Counts ---")
        for (table_name,) in tables:
            try:
                count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"  {table_name}: {count:,} rows")
            except Exception as e:
                print(f"  {table_name}: Error - {e}")
        
        # Step 5: List views (if any)
        print("\n--- Views ---")
        views = con.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'main' AND table_type = 'VIEW'
        """).fetchall()
        
        if views:
            for i, (view_name,) in enumerate(views, 1):
                print(f"  {i}. {view_name}")
        else:
            print("  No views found.")
        
        print("\n" + "=" * 60)
        print("Complete!")
        print("=" * 60)
        
    finally:
        # Step 6: Close the connection
        con.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    list_all_tables()
