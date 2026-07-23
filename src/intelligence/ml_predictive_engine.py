import json
import duckdb
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor


try:
    from src.config import DB_PATH as _CONFIG_DB_PATH
    DB_PATH = str(_CONFIG_DB_PATH)
except Exception:
    DB_PATH = "data/warehouse/retail.duckdb"


# fact_inventory only stores stock_level/reorder_point per (product_key,
# store_key, date_key) snapshot; product_id/store_id/category and sales
# velocity have to be derived by joining to dim_product/dim_store/fact_sales.
_TRAINING_QUERY = """
    WITH latest_inventory AS (
        SELECT
            product_key,
            store_key,
            stock_level,
            ROW_NUMBER() OVER (
                PARTITION BY product_key, store_key
                ORDER BY date_key DESC
            ) AS rn
        FROM fact_inventory
    ),
    sales_stats AS (
        SELECT
            product_key,
            store_key,
            AVG(quantity) AS avg_sales_7d,
            COALESCE(STDDEV(quantity), 0) AS stddev_sales_7d
        FROM fact_sales
        GROUP BY product_key, store_key
    )
    SELECT
        dp.product_id,
        ds.store_id,
        dp.category,
        li.stock_level AS current_stock,
        COALESCE(ss.avg_sales_7d, 0) AS avg_sales_7d,
        COALESCE(ss.stddev_sales_7d, 0) AS stddev_sales_7d
    FROM latest_inventory li
    JOIN dim_product dp ON dp.product_key = li.product_key
    JOIN dim_store ds ON ds.store_key = li.store_key
    LEFT JOIN sales_stats ss
        ON ss.product_key = li.product_key AND ss.store_key = li.store_key
    WHERE li.rn = 1
"""


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

        self.category_map = {}
        self._single_class_risk = None  # set if training data has only one risk class

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


    def _encode_category(self, category, fit: bool = False) -> int:
        """Stable label-encoding for dim_product.category, shared between
        training and prediction. Unseen categories at prediction time map to
        a dedicated 'unknown' bucket rather than crashing or re-encoding."""
        if fit and category not in self.category_map:
            self.category_map[category] = len(self.category_map)
        return self.category_map.get(category, len(self.category_map))


    # =========================
    # TRAINING
    # =========================
    def _train_models(self):

        df = self.con.execute(_TRAINING_QUERY).fetchdf()

        if df.empty:
            return

        df["category_encoded"] = df["category"].apply(lambda c: self._encode_category(c, fit=True))

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

        if y_class.nunique() < 2:
            # RandomForestClassifier can't fit/predict_proba meaningfully with
            # a single class present; remember the constant instead.
            self._single_class_risk = int(y_class.iloc[0])
        else:
            self._single_class_risk = None
            self.classifier.fit(X, y_class)

        self.regressor.fit(X, y_reg)


    # =========================
    # PREDICTION
    # =========================
    def predict_stockout_with_explanation(self, product_id, store_id):

        df = self.con.execute(
            f"""
            SELECT * FROM ({_TRAINING_QUERY}) t
            WHERE t.product_id = ? AND t.store_id = ?
            LIMIT 1
            """,
            [product_id, store_id],
        ).fetchdf()

        if df.empty:
            return None

        df["category_encoded"] = df["category"].apply(lambda c: self._encode_category(c, fit=False))

        features = [
            "current_stock",
            "avg_sales_7d",
            "stddev_sales_7d",
            "category_encoded"
        ]

        X = df[features]

        if self._single_class_risk is not None:
            risk_prob = float(self._single_class_risk)
        else:
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

        current_stock = float(df["current_stock"].iloc[0])
        avg_sales_7d = float(df["avg_sales_7d"].iloc[0])
        stddev_sales_7d = float(df["stddev_sales_7d"].iloc[0])
        volatility_cv = round(stddev_sales_7d / avg_sales_7d, 2) if avg_sales_7d > 0 else 0.0

        explanation = {
            "risk_level": level,
            "ml_confidence": round(risk_prob * 100, 2),
            "current_stock": current_stock,
            "avg_daily_demand": avg_sales_7d,
            "volatility_cv": volatility_cv,
        }

        result = {
            "recommended_reorder": reorder_qty,
            "confidence": risk_prob,
            "explanation": explanation
        }

        self._log_decision(product_id, store_id, reorder_qty, risk_prob, explanation)

        return result


    def _log_decision(self, product_id, store_id, reorder_qty, risk_prob, explanation) -> None:
        """Append this prediction to ml_reasoning_log so it's visible to
        kpi.get_ai_decisions() and the Streamlit reasoning explorer."""
        next_id = self.con.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM ml_reasoning_log"
        ).fetchone()[0]

        self.con.execute(
            """
            INSERT INTO ml_reasoning_log
                (id, timestamp, model_name, product_id, store_id, prediction, confidence, explanation_json)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
            """,
            [
                next_id,
                "stockout_risk_classifier",
                product_id,
                store_id,
                float(reorder_qty),
                float(risk_prob),
                json.dumps(explanation),
            ],
        )


if __name__ == "__main__":
    print("Training stockout classifier + reorder regressor on current fact_inventory/fact_sales data...")
    engine = MLPredictiveEngine()
    print(f"Done. Category encoding: {engine.category_map}")
    if engine._single_class_risk is not None:
        print(f"Note: training data had only one risk class ({engine._single_class_risk}); classifier not fit.")
