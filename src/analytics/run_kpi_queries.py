"""
Execute KPI queries from kpi_queries.sql file.
Run: python src/analytics/run_kpi_queries.py
"""

import duckdb
from pathlib import Path

DB_PATH = "data/warehouse/retail.duckdb"
SQL_FILE = "src/analytics/kpi_queries.sql"


def execute_kpi_queries():
    """Execute all KPI queries from the SQL file"""
    
    print("=" * 60)
    print("Executing KPI Queries")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"SQL File: {SQL_FILE}")
    print("=" * 60)
    
    # Check if SQL file exists
    sql_path = Path(SQL_FILE)
    if not sql_path.exists():
        print(f"ERROR: SQL file not found: {SQL_FILE}")
        return
    
    # Connect to DuckDB
    # If you get a lock error, close any open DuckDB CLI sessions first
    try:
        con = duckdb.connect(DB_PATH)
    except Exception as e:
        if "lock" in str(e).lower() or "conflicting" in str(e).lower():
            print("\n⚠️  DATABASE LOCK ERROR:")
            print("   Another DuckDB process is using the database.")
            print("\n   Solutions:")
            print("   1. Close any open DuckDB CLI sessions:")
            print("      - Go to the terminal where DuckDB CLI is running")
            print("      - Type: .exit")
            print("      - Or press Ctrl+D")
            print("   2. Or wait a few seconds and try again")
            print("   3. Or find and kill the process:")
            print("      - Find PID: lsof data/warehouse/retail.duckdb")
            print("      - Kill it: kill <PID>")
            print(f"\n   Error details: {e}")
            return
        else:
            raise
    
    try:
        # Read the SQL file
        print(f"\nReading SQL file: {SQL_FILE}")
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Remove full-line comments so queries don't start with '--'
        # Then split by semicolons to get individual statements.
        cleaned_lines = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("--"):
                continue
            cleaned_lines.append(line)

        cleaned_sql = "\n".join(cleaned_lines)
        queries = [q.strip() for q in cleaned_sql.split(";") if q.strip()]
        
        print(f"Found {len(queries)} query/queries to execute\n")
        
        # Execute each query
        for i, query in enumerate(queries, 1):
            # Skip empty queries and comments-only blocks
            if not query or query.startswith('--'):
                continue
            
            try:
                print(f"\n{'='*60}")
                print(f"Query {i}/{len(queries)}")
                print(f"{'='*60}")
                
                # Execute query.
                # If it's a SELECT/WITH, fetch a dataframe to display results.
                lowered = query.lstrip().lower()
                is_select_like = lowered.startswith("select") or lowered.startswith("with")

                if is_select_like:
                    result = con.execute(query).fetchdf()
                else:
                    con.execute(query)
                    result = None
                
                # Display results
                if result is not None and not result.empty:
                    print(f"\nResults ({len(result)} rows):")
                    print(result.to_string(index=False))
                else:
                    print("\nQuery executed successfully (no rows returned)")
                    
            except Exception as e:
                print(f"\n⚠️  Error executing query {i}:")
                print(f"   {str(e)}")
                print(f"\n   Query preview: {query[:100]}...")
                continue
        
        print("\n" + "=" * 60)
        print("KPI Queries Execution Complete!")
        print("=" * 60)
        
    finally:
        con.close()
        print("\nConnection closed.")


def execute_all_at_once():
    """Execute entire SQL file as one block (simpler, but less control)"""
    
    print("=" * 60)
    print("Executing KPI Queries (All at Once)")
    print("=" * 60)
    
    sql_path = Path(SQL_FILE)
    if not sql_path.exists():
        print(f"ERROR: SQL file not found: {SQL_FILE}")
        return
    
    try:
        con = duckdb.connect(DB_PATH)
    except Exception as e:
        if "lock" in str(e).lower() or "conflicting" in str(e).lower():
            print("\n⚠️  DATABASE LOCK ERROR:")
            print("   Another DuckDB process is using the database.")
            print("\n   Solutions:")
            print("   1. Close any open DuckDB CLI sessions:")
            print("      - Go to the terminal where DuckDB CLI is running")
            print("      - Type: .exit")
            print("      - Or press Ctrl+D")
            print("   2. Or wait a few seconds and try again")
            print(f"\n   Error details: {e}")
            return
        else:
            raise
    
    try:
        # Read entire SQL file
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Execute all queries
        # Note: DuckDB will execute all statements sequentially
        print("Executing all queries...\n")
        con.execute(sql_content)
        
        print("✓ All queries executed successfully!")
        print("\nNote: Some queries may not return results (CREATE, INSERT, etc.)")
        print("      Use DuckDB CLI or individual SELECT queries to view results.")
        
    except Exception as e:
        print(f"\n⚠️  Error: {str(e)}")
    finally:
        con.close()


if __name__ == "__main__":
    import sys
    
    # Check command line argument
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        execute_all_at_once()
    else:
        execute_kpi_queries()
