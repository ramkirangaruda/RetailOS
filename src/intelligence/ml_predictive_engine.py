from datetime import datetime


class MLPredictiveEngine:

    def __init__(self, connection):
        self.con = connection
        print("ML Engine attached to existing DB connection.")

    def predict_stockout_with_explanation(self, product_id, store_id):

        try:
            df = self.con.execute("""
                SELECT 
                    fi.stock_level,
                    fi.reorder_point,
                    dp.product_key,
                    ds.store_key
                FROM fact_inventory fi
                JOIN dim_product dp ON fi.product_key = dp.product_key
                JOIN dim_store ds ON fi.store_key = ds.store_key
                WHERE dp.product_id = ?
                AND ds.store_id = ?
                LIMIT 1
            """, [product_id, store_id]).fetchdf()

            if df.empty:
                return None

        except Exception as e:
            print("ML Query error:", e)
            return None

        stock = int(df["stock_level"][0])
        reorder_point = int(df["reorder_point"][0])
        product_key = int(df["product_key"][0])
        store_key = int(df["store_key"][0])

        # Risk Logic
        if stock <= reorder_point * 0.5:
            level = "Critical"
            confidence = 92.5
        elif stock <= reorder_point:
            level = "High"
            confidence = 81.3
        elif stock <= reorder_point * 1.5:
            level = "Medium"
            confidence = 64.7
        else:
            level = "Low"
            confidence = 35.2

        recommended_reorder = max(reorder_point * 2 - stock, 0)

        if level in ["High", "Critical"]:

            existing = self.con.execute("""
                SELECT COUNT(*)
                FROM ml_alerts
                WHERE product_id = ?
                AND store_id = ?
                AND timestamp >= NOW() - INTERVAL 5 MINUTE
            """, [product_id, store_id]).fetchone()[0]

            if existing == 0:

                self.con.execute("""
                    INSERT INTO ml_alerts
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    datetime.now(),
                    product_id,
                    store_id,
                    level,
                    confidence,
                    recommended_reorder
                ])

                next_id = self.con.execute("""
                    SELECT COALESCE(MAX(reorder_id), 0) + 1
                    FROM auto_reorders
                """).fetchone()[0]

                self.con.execute("""
                    INSERT INTO auto_reorders
                    (reorder_id, timestamp, product_id, store_id, reorder_quantity, trigger_reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    next_id,
                    datetime.now(),
                    product_key,
                    store_key,
                    recommended_reorder,
                    "AUTO-ML"
                ])

                print(f"🚨 ALERT TRIGGERED: {product_id} | {store_id} | {level}")

        return {
            "recommended_reorder": recommended_reorder,
            "explanation": {
                "risk_level": level,
                "ml_confidence": confidence
            }
        }
