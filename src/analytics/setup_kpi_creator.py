#!/usr/bin/env python3
"""
Setup script to create the create_kpi_tables.py file
Run this first: python3 setup_kpi_creator.py
Then run: python3 create_kpi_tables.py
"""

from pathlib import Path

def create_kpi_tables_script():
    """Create the create_kpi_tables.py file"""
    
    script_content = '''#!/usr/bin/env python3
"""
Create materialized KPI tables in DuckDB database
"""

import duckdb
from pathlib import Path
import sys

def create_kpi_tables():
    # Connect to database
    db_path = 'data/warehouse/retail.duckdb'
    
    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        print("Run: python3 data_generator.py first")
        sys.exit(1)
    
    print("="*80)
    print("CREATING KPI TABLES IN DUCKDB DATABASE")
    print("="*80)
    
    con = duckdb.connect(db_path)
    
    # KPI 1: Daily Revenue
    print("\\n1. Creating kpi_daily_revenue...")
    con.execute("""
    CREATE OR REPLACE TABLE kpi_daily_revenue AS
    SELECT 
        dd.date,
        dd.year,
        dd.month,
        dd.day,
        CASE dd.is_weekend WHEN true THEN 'Weekend' ELSE 'Weekday' END as day_type,
        SUM(fs.revenue) as daily_revenue,
        COUNT(fs.sale_id) as transaction_count,
        AVG(fs.revenue) as avg_transaction_value,
        SUM(fs.quantity) as total_units_sold
    FROM fact_sales fs
    JOIN dim_date dd ON fs.date_key = dd.date_key
    GROUP BY dd.date, dd.year, dd.month, dd.day, dd.is_weekend
    ORDER BY dd.date DESC;
    """)
    row_count = con.execute("SELECT COUNT(*) FROM kpi_daily_revenue").fetchone()[0]
    print(f"   ✓ Created with {row_count:,} rows")
    
    # KPI 2: Monthly Revenue
    print("\\n2. Creating kpi_monthly_revenue...")
    con.execute("""
    CREATE OR REPLACE TABLE kpi_monthly_revenue AS
    SELECT 
        dd.year,
        dd.month,
        SUM(fs.revenue) as monthly_revenue,
        COUNT(fs.sale_id) as transaction_count,
        AVG(fs.revenue) as avg_transaction_value,
        SUM(fs.quantity) as total_units_sold
    FROM fact_sales fs
    JOIN dim_date dd ON fs.date_key = dd.date_key
    GROUP BY dd.year, dd.month
    ORDER BY dd.year, dd.month;
    """)
    row_count = con.execute("SELECT COUNT(*) FROM kpi_monthly_revenue").fetchone()[0]
    print(f"   ✓ Created with {row_count:,} rows")
    
    # KPI 3: City-wise Sales
    print("\\n3. Creating kpi_city_sales...")
    con.execute("""
    CREATE OR REPLACE TABLE kpi_city_sales AS
    SELECT 
        ds.city,
        ds.region,
        COUNT(DISTINCT fs.store_key) as active_stores,
        SUM(fs.revenue) as total_revenue,
        COUNT(fs.sale_id) as transaction_count,
        AVG(fs.revenue) as avg_transaction_value
    FROM fact_sales fs
    JOIN dim_store ds ON fs.store_key = ds.store_key
    GROUP BY ds.city, ds.region
    ORDER BY total_revenue DESC;
    """)
    row_count = con.execute("SELECT COUNT(*) FROM kpi_city_sales").fetchone()[0]
    print(f"   ✓ Created with {row_count:,} rows")
    
    # KPI 4: Top Selling Products
    print("\\n4. Creating kpi_top_products...")
    con.execute("""
    CREATE OR REPLACE TABLE kpi_top_products AS
    SELECT 
        dp.product_id,
        dp.name as product_name,
        dp.category,
        dp.brand,
        SUM(fs.quantity) as total_quantity_sold,
        SUM(fs.revenue) as total_revenue,
        COUNT(fs.sale_id) as transaction_count
    FROM fact_sales fs
    JOIN dim_product dp ON fs.product_key = dp.product_key
    GROUP BY dp.product_id, dp.name, dp.category, dp.brand
    ORDER BY total_revenue DESC;
    """)
    row_count = con.execute("SELECT COUNT(*) FROM kpi_top_products").fetchone()[0]
    print(f"   ✓ Created with {row_count:,} rows")
    
    # KPI 5: Inventory Turnover
    print("\\n5. Creating kpi_inventory_turnover...")
    con.execute("""
    CREATE OR REPLACE TABLE kpi_inventory_turnover AS
    SELECT 
        dp.product_id,
        dp.name as product_name,
        dp.category,
        SUM(fs.quantity) as total_sold,
        COUNT(DISTINCT fs.date_key) as days_sold,
        SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0) as avg_daily_sales,
        CASE 
            WHEN SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0) > 10 THEN 'Fast Moving'
            WHEN SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0) > 2 THEN 'Medium Moving'
            ELSE 'Slow Moving'
        END as movement_category
    FROM fact_sales fs
    JOIN dim_product dp ON fs.product_key = dp.product_key
    GROUP BY dp.product_id, dp.name, dp.category
    ORDER BY avg_daily_sales DESC;
    """)
    row_count = con.execute("SELECT COUNT(*) FROM kpi_inventory_turnover").fetchone()[0]
    print(f"   ✓ Created with {row_count:,} rows")
    
    # KPI 6: Summary Dashboard
    print("\\n6. Creating kpi_summary_dashboard...")
    con.execute("""
    CREATE OR REPLACE TABLE kpi_summary_dashboard AS
    SELECT 'Total Revenue' as metric, CAST(SUM(revenue) AS VARCHAR) as value FROM fact_sales
    UNION ALL
    SELECT 'Total Transactions', CAST(COUNT(sale_id) AS VARCHAR) FROM fact_sales
    UNION ALL
    SELECT 'Total Customers', CAST(COUNT(DISTINCT customer_key) AS VARCHAR) FROM fact_sales
    UNION ALL
    SELECT 'Total Products', CAST(COUNT(DISTINCT product_key) AS VARCHAR) FROM fact_sales
    UNION ALL
    SELECT 'Avg Transaction Value', CAST(ROUND(AVG(revenue), 2) AS VARCHAR) FROM fact_sales;
    """)
    row_count = con.execute("SELECT COUNT(*) FROM kpi_summary_dashboard").fetchone()[0]
    print(f"   ✓ Created with {row_count:,} rows")
    
    # Summary
    print("\\n" + "="*80)
    print("KPI TABLES CREATED SUCCESSFULLY")
    print("="*80)
    
    all_tables = con.execute("SHOW TABLES").fetchall()
    kpi_tables = sorted([t[0] for t in all_tables if t[0].startswith('kpi_')])
    
    print("\\nKPI Tables in Database:")
    print("-"*80)
    for table in kpi_tables:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:40} {count:>10,} rows")
    
    con.close()
    print("\\n✓ Ready to export! Run: python3 export_kpi_tables.py")

if __name__ == "__main__":
    create_kpi_tables()
'''
    
    # Write to file
    output_file = Path('create_kpi_tables.py')
    output_file.write_text(script_content)
    
    # Make executable (Unix/Linux/Mac)
    try:
        import os
        os.chmod(output_file, 0o755)
    except:
        pass
    
    print("="*80)
    print("SETUP COMPLETE")
    print("="*80)
    print(f"\n✓ Created file: {output_file.absolute()}")
    print(f"\nNext steps:")
    print(f"  1. Run: python3 create_kpi_tables.py")
    print(f"  2. Run: python3 export_kpi_tables.py")

if __name__ == "__main__":
    create_kpi_tables_script()