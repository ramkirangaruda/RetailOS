# tests/test_ml_engine.py
import sys
import os

# Windows consoles default to a codepage that can't print this script's
# emoji status markers - force UTF-8 so that doesn't crash the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.intelligence.ml_predictive_engine import MLPredictiveEngine
import duckdb
import traceback

def main():
    print("=== TESTING ML PREDICTIVE ENGINE ===\n")

    try:
        # Connect to DuckDB
        con = duckdb.connect("data/warehouse/retail.duckdb")

        # Initialize engine. MLPredictiveEngine has no separate
        # train_stockout_classifier()/train_reorder_amount_regressor()
        # methods - both models train automatically inside __init__ (see
        # _train_models()), so constructing the engine IS the training step.
        print("1️⃣ Training stockout classifier + reorder regressor...")
        engine = MLPredictiveEngine()
        if engine._single_class_risk is not None:
            print(f"⚠️ Training data had only one risk class ({engine._single_class_risk}); classifier not fit.\n")
        else:
            print(f"✅ Trained. Category encoding: {engine.category_map}\n")

        # -------------------------------
        # Test 3: Make Sample Prediction
        # -------------------------------
        print("3️⃣ Making a Sample Prediction...")
        result = engine.predict_stockout_with_explanation(
            product_id='P0000',
            store_id='ST000'
        )

        print(f"✅ Risk Level: {result['explanation']['risk_level']}")
        print(f"✅ Confidence: {result['confidence']:.1%}")
        print(f"✅ Recommended Reorder: {result['recommended_reorder']} units\n")

        # -------------------------------
        # Test 4: Verify Logging
        # -------------------------------
        print("4️⃣ Checking ML Reasoning Log...")
        logged = con.execute(
            "SELECT COUNT(*) FROM ml_reasoning_log"
        ).fetchone()[0]

        print(f"✅ {logged} predictions logged in database\n")

        print("=== ALL ML TESTS COMPLETED ===")

    except Exception as e:
        print("❌ TEST FAILED")
        print("Error details:")
        traceback.print_exc()

    finally:
        try:
            con.close()
        except:
            pass


if __name__ == "__main__":
    main()
