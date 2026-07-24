import sys

from src.ingestion.adaptive_schema_manager import AdaptiveSchemaManager
import pandas as pd
import duckdb

# Windows consoles default to a codepage that can't print this script's
# emoji status markers - force UTF-8 so that doesn't crash the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if __name__ == "__main__":

    print("=== TESTING SCHEMA MANAGER ===\n")

    manager = AdaptiveSchemaManager()
    manager.initialize_registry()

    # Test 1
    print("1️⃣ Normal data...")
    normal_df = pd.DataFrame({
        'transaction_id': [1, 2, 3],
        'product_id': [10, 20, 30],
        'store_id': [1, 1, 2],
        'timestamp': pd.date_range('2024-01-01', periods=3),
        'quantity': [2, 3, 1],
        'price': [100.0, 200.0, 150.0]
    })

    result = manager.process_ingestion_with_adaptive_schema("transactions", normal_df)
    print(result, "\n")

    # Test 2
    print("2️⃣ One new column...")
    df2 = normal_df.copy()
    df2["payment_method"] = ["UPI", "Card", "Cash"]

    result = manager.process_ingestion_with_adaptive_schema("transactions", df2)
    print(result, "\n")

    # Test 3
    print("3️⃣ Six noisy columns...")
    df3 = normal_df.copy()
    for i in range(6):
        df3[f"random_{i}"] = ["???", "xxx", "###"]

    result = manager.process_ingestion_with_adaptive_schema("transactions", df3)
    print(result, "\n")

    con = duckdb.connect("data/warehouse/retail.duckdb")

    changes = con.execute("SELECT COUNT(*) FROM schema_change_log").fetchone()[0]
    queue = con.execute("SELECT COUNT(*) FROM schema_approval_queue").fetchone()[0]

    print("Logged changes:", changes)
    print("Queued approvals:", queue)

    print("\n=== DONE ===")
