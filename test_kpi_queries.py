#!/usr/bin/env python3
"""
Test script for KPI queries
Validates each KPI query and provides sample output
"""

import duckdb
import os
import sys
from pathlib import Path

# Windows consoles default to a codepage (e.g. cp1252) that can't print
# non-ASCII characters this script's output includes (e.g. the Rupee sign
# in kpi_queries.sql's summary query) - force UTF-8 so a query that
# succeeded doesn't get reported as [FAIL] just because print() choked.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = "data/warehouse/retail.duckdb"
KPI_QUERIES_FILE = "src/analytics/kpi_queries.sql"

def test_database_connection():
    """Test if database is accessible"""
    try:
        con = duckdb.connect(DB_PATH)
        tables = con.execute("SHOW TABLES").fetchdf()
        print(f"[OK] Database connected successfully", flush=True)
        print(f"[OK] Available tables: {', '.join(tables['name'].tolist())}", flush=True)
        
        # Check fact_sales data
        count = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
        print(f"[OK] fact_sales has {count:,} rows", flush=True)
        
        con.close()
        return True
    except Exception as e:
        print(f"[FAIL] Database connection failed: {e}", flush=True)
        return False

def test_kpi_queries():
    """Test each KPI query"""
    if not os.path.exists(KPI_QUERIES_FILE):
        print(f"[FAIL] KPI queries file not found: {KPI_QUERIES_FILE}", flush=True)
        return False
    
    try:
        con = duckdb.connect(DB_PATH)
        
        with open(KPI_QUERIES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by KPI sections
        kpi_sections = content.split('-- =====================================================')[1:]
        
        print(f"\n[INFO] Testing {len(kpi_sections)} KPI queries...\n", flush=True)
        
        for i, section in enumerate(kpi_sections, 1):
            lines = section.strip().split('\n')
            title_line = next((line for line in lines if line.strip().startswith('--')), '')
            title = title_line.replace('--', '').strip() if title_line else f"KPI {i}"
            
            # Extract the query (between comments)
            query_lines = []
            in_query = False
            
            for line in lines:
                if line.strip().startswith('-- Description:') or line.strip().startswith('-- Business Use:') or line.strip().startswith('-- Dependencies:'):
                    continue
                if not line.strip().startswith('--') and line.strip():
                    in_query = True
                if in_query and line.strip():
                    query_lines.append(line)
                elif in_query and line.strip().startswith('--') and 'Additional Utility' not in line:
                    break
            
            if query_lines:
                query = '\n'.join(query_lines)
                
                try:
                    result = con.execute(query).fetchdf()
                    print(f"[OK] {title}", flush=True)
                    print(f"  Rows returned: {len(result)}", flush=True)
                    if len(result) > 0:
                        print(f"  Sample columns: {', '.join(result.columns[:3])}{'...' if len(result.columns) > 3 else ''}", flush=True)
                        if len(result) > 0:
                            sample_data = result.head(2).to_string(index=False, max_cols=3)
                            # Replace newline with indented newline
                            print(f"  Sample data:\n    {sample_data.replace(chr(10), chr(10) + '    ')}", flush=True)
                    print("", flush=True)
                    
                except Exception as e:
                    print(f"[FAIL] {title} - Error: {e}", flush=True)
                    print(f"  Query: {query[:100]}...\n", flush=True)
        
        con.close()
        return True
        
    except Exception as e:
        print(f"[FAIL] Error testing KPI queries: {e}", flush=True)
        return False

def test_rbac_views():
    """Test RBAC views creation"""
    try:
        from src.storage.access_control import create_rbac_views

        print("[INFO] Testing RBAC views creation...", flush=True)
        con = duckdb.connect(DB_PATH)
        create_rbac_views(con)

        # Test each view
        views = ['analyst_sales', 'store_manager_sales', 'finance_sales', 'admin_all']
        
        for view in views:
            try:
                result = con.execute(f"SELECT COUNT(*) FROM {view} LIMIT 1").fetchone()
                print(f"[OK] View {view} accessible", flush=True)
            except Exception as e:
                print(f"[FAIL] View {view} failed: {e}", flush=True)
        
        con.close()
        return True
        
    except Exception as e:
        print(f"[FAIL] RBAC views test failed: {e}", flush=True)
        # Import error might happen if src is not in path, but simple script usually works.
        return False

def main():
    """Main test function"""
    print("RetailOS KPI and RBAC Testing\n", flush=True)
    
    # Test database connection
    if not test_database_connection():
        sys.exit(1)
    
    # Test RBAC views
    test_rbac_views()
    
    # Test KPI queries
    test_kpi_queries()
    
    print("[DONE] Testing completed!", flush=True)

if __name__ == "__main__":
    main()
