import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor


try:
    from src.config import DB_PATH as _CONFIG_DB_PATH
    DB_PATH = str(_CONFIG_DB_PATH)
except Exception:
    DB_PATH = "data/warehouse/retail.duckdb"


class MLPredictiveEngine:

    def __init__(self):
        self.con = duckdb.connect(DB_PATH)

        self._ensure_runtime_tables()

        self.classifier = RandomForestClassifier(
            n_estimators=50,
            random_state=42
        )

        self.regressor = GradientBoostingRegressor(
            random_state=42
        )

        self._train_models()


    def _ensure_runtime_tables(self) -> None:
        # Used by Streamlit dashboards and verification scripts.
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS ml_reasoning_log (
                id BIGINT,
                timestamp TIMESTAMP,
                model_name VARCHAR,
                product_id VARCHAR,
                store_id VARCHAR,
                prediction DOUBLE,
                confidence DOUBLE,
                explanation_json VARCHAR
            )
        """)


    # =========================
    # TRAINING
    # =========================
    def _train_models(self):

        try:
            df = self.con.execute("""
                SELECT 
                    product_id,
                    store_id,
                    current_stock,
                    avg_sales_7d,
                    stddev_sales_7d,
                    category_encoded
                FROM fact_inventory
                LIMIT 500
            """).fetchdf()
        except:
            # fallback dummy training
            df = pd.DataFrame({
                "current_stock": np.random.randint(1, 100, 200),
                "avg_sales_7d": np.random.randint(1, 50, 200),
                "stddev_sales_7d": np.random.randint(1, 20, 200),
                "category_encoded": np.random.randint(0, 5, 200)
            })

        if df.empty:
            return

        df["risk"] = (df["current_stock"] < df["avg_sales_7d"]).astype(int)
        df["reorder_qty"] = np.maximum(
            df["avg_sales_7d"] * 2 - df["current_stock"],
            0
        )

        features = [
            "current_stock",
            "avg_sales_7d",
            "stddev_sales_7d",
            "category_encoded"
        ]

        X = df[features]
        y_class = df["risk"]
        y_reg = df["reorder_qty"]

        self.classifier.fit(X, y_class)
        self.regressor.fit(X, y_reg)


    # =========================
    # PREDICTION
    # =========================
    def predict_stockout_with_explanation(self, product_id, store_id):

        try:
            df = self.con.execute(f"""
                SELECT 
                    current_stock,
                    avg_sales_7d,
                    stddev_sales_7d,
                    category_encoded
                FROM fact_inventory
                WHERE product_id = '{product_id}'
                AND store_id = '{store_id}'
                LIMIT 1
            """).fetchdf()

            if df.empty:
                return None

        except:
            return None

        features = [
            "current_stock",
            "avg_sales_7d",
            "stddev_sales_7d",
            "category_encoded"
        ]

        X = df[features]

        risk_prob = self.classifier.predict_proba(X)[0][1]
        reorder_qty = int(self.regressor.predict(X)[0])

        if risk_prob > 0.8:
            level = "Critical"
        elif risk_prob > 0.6:
            level = "High"
        elif risk_prob > 0.4:
            level = "Medium"
        else:
            level = "Low"

        explanation = {
            "risk_level": level,
            "ml_confidence": round(risk_prob * 100, 2)
        }

        return {
            "recommended_reorder": reorder_qty,
            "explanation": explanation
        }
