import sys
import os
import pandas as pd
import duckdb
import asyncio
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

def print_status(component, status, message=""):
    icon = "[OK]" if status else "[FAIL]"
    print(f"{icon} {component}: {message}")

def verify_config():
    try:
        import config
        if not config.DB_PATH.parent.exists():
            return False, "Data directory missing"
        return True, "Loaded and paths valid"
    except Exception as e:
        return False, str(e)

def verify_database():
    try:
        import config
        con = duckdb.connect(str(config.DB_PATH))
        con.execute("SELECT 1").fetchone()
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)

def verify_schema_manager():
    try:
        from ingestion.adaptive_schema_manager import AdaptiveSchemaManager
        manager = AdaptiveSchemaManager()
        manager.initialize_registry()
        
        # Test detection against a known registered schema
        df = pd.DataFrame({
            'transaction_id': [1],
            'product_id': [10],
            'store_id': [1],
            'timestamp': pd.to_datetime(['2024-01-01']),
            'quantity': [2],
            'price': [100.0],
            'new_col': [1.5],
        })
        changes, missing = manager.detect_schema_changes('transactions', df)
        
        if len(changes) > 0:
            return True, f"Initialized and detected {len(changes)} changes"
        return False, "Failed to detect changes"
    except Exception as e:
        return False, str(e)

def verify_ml_engine():
    try:
        from intelligence.ml_predictive_engine import MLPredictiveEngine
        engine = MLPredictiveEngine()
        # Just check if it initialized and created tables
        engine.con.execute("SELECT COUNT(*) FROM ml_reasoning_log").fetchone()
        return True, "Initialized and DB tables ready"
    except Exception as e:
        return False, str(e)

def verify_scheduler():
    try:
        from ingestion.batch_scheduler import BatchPipelineScheduler
        sched = BatchPipelineScheduler()
        return True, "Initialized successfully"
    except Exception as e:
        return False, str(e)

def verify_websocket():
    try:
        from ingestion.websocket_streaming import WebSocketOrderStream
        ws = WebSocketOrderStream()
        return True, "Initialized successfully"
    except Exception as e:
        return False, str(e)

async def main():
    print("Starting System Runtime Verification...\n")
    
    components = [
        ("Configuration", verify_config),
        ("Database", verify_database),
        ("Adapter Schema Manager", verify_schema_manager),
        ("ML Predictive Engine", verify_ml_engine),
        ("Batch Scheduler", verify_scheduler),
        ("WebSocket Stream", verify_websocket)
    ]
    
    results = {}
    
    for name, func in components:
        # Check if async
        if asyncio.iscoroutinefunction(func):
            success, msg = await func()
        else:
            success, msg = func()
        
        print_status(name, success, msg)
        results[name] = success
        
    print("\n" + "="*30)
    if all(results.values()):
        print("SYSTEM READY: All components verified.")
    else:
        print("SYSTEM ISSUES DETECTED: Some components failed.")
        
if __name__ == "__main__":
    asyncio.run(main())
