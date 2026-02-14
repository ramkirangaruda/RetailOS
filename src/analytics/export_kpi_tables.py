#!/usr/bin/env python3
"""
Export all KPI tables from DuckDB to CSV files
Usage: python3 export_kpi_tables.py
"""

import duckdb
from pathlib import Path
import sys

def export_kpi_tables():
    """Export all KPI tables to CSV files"""
    
    # Database path
    db_path = 'data/warehouse/retail.duckdb'
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        print("Please run: python3 data_generator.py first")
        sys.exit(1)
    
    # Connect to database
    try:
        con = duckdb.connect(db_path)
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)
    
    # Create export directory
    export_dir = Path('output/kpi_tables_export')
    export_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("EXPORTING KPI TABLES TO CSV")
    print("=" * 80)
    
    # Get all KPI tables
    try:
        all_tables = con.execute("SHOW TABLES").fetchall()
        kpi_tables = sorted([t[0] for t in all_tables if t[0].startswith('kpi_')])
    except Exception as e:
        print(f"❌ Error fetching tables: {e}")
        con.close()
        sys.exit(1)
    
    # Check if KPI tables exist
    if not kpi_tables:
        print("\n⚠ No KPI tables found in database!")
        print("Please run: python3 create_kpi_tables.py first")
        con.close()
        sys.exit(1)
    
    print(f"\nFound {len(kpi_tables)} KPI tables to export\n")
    
    # Export each table
    exported_count = 0
    failed_count = 0
    
    for table in kpi_tables:
        try:
            output_file = export_dir / f"{table}.csv"
            
            # Export to CSV using DuckDB COPY
            con.execute(f"""
            COPY (SELECT * FROM {table}) 
            TO '{output_file}' 
            (HEADER, DELIMITER ',')
            """)
            
            # Get file size
            if output_file.exists():
                size_kb = output_file.stat().st_size / 1024
                row_count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"✓ {table:40} → {output_file.name:30} ({row_count:>6,} rows, {size_kb:>8.1f} KB)")
                exported_count += 1
            else:
                print(f"⚠ {table:40} → Export failed (file not created)")
                failed_count += 1
                
        except Exception as e:
            print(f"❌ {table:40} → Error: {e}")
            failed_count += 1
    
    con.close()
    
    # Summary
    print("\n" + "=" * 80)
    print("EXPORT SUMMARY")
    print("=" * 80)
    print(f"Successfully exported: {exported_count} tables")
    if failed_count > 0:
        print(f"Failed to export:      {failed_count} tables")
    print(f"\n✓ All files saved to: {export_dir.absolute()}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"""
You can now:
  1. Open CSV files in Excel/Google Sheets:
     cd {export_dir}
     
  2. Import into Power BI/Tableau:
     - File → Import → CSV
     - Select files from: {export_dir.absolute()}
     
  3. View files:
     ls -lh {export_dir}
     
  4. Read a specific file:
     head {export_dir}/kpi_daily_revenue.csv
    """)
    
    return exported_count, failed_count

if __name__ == "__main__":
    try:
        exported, failed = export_kpi_tables()
        sys.exit(0 if failed == 0 else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Export cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)