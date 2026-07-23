from __future__ import annotations

import json

from src.storage.warehouse import get_connection

def get_daily_revenue():
    """Get daily revenue for the last 30 days"""
    with get_connection(read_only=True) as con:
        result = con.execute(
            """
            SELECT d.date, SUM(f.revenue) as total_revenue
            FROM fact_sales f
            JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.date
            ORDER BY d.date DESC
            LIMIT 30
            """
        ).fetchall()

        return [{"date": str(r[0]), "revenue": float(r[1])} for r in result]


def get_city_sales():
    """Get city-wise sales performance with detailed metrics"""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            SELECT
                ds.city,
                ds.region,
                COUNT(DISTINCT fs.store_key) as active_stores,
                SUM(fs.revenue) as total_revenue,
                COUNT(fs.sale_id) as transaction_count,
                AVG(fs.revenue) as avg_transaction_value,
                SUM(fs.quantity) as total_units_sold,
                ROUND(SUM(fs.revenue) * 100.0 / SUM(SUM(fs.revenue)) OVER (), 2) as revenue_share_pct
            FROM fact_sales fs
            JOIN dim_store ds ON fs.store_key = ds.store_key
            GROUP BY ds.city, ds.region
            ORDER BY total_revenue DESC
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_customer_distribution():
    """Get customer distribution by city with tier and value segmentation.

    avg_clv is the average per-customer lifetime revenue (aggregated per
    customer first, then averaged within the city) rather than the average
    transaction value. customer_lifespan_days is computed from real
    dim_date.date values, not from date_key (an integer in YYYYMMDD form,
    which is not safe to subtract directly across month/year boundaries).
    """
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            WITH customer_agg AS (
                SELECT
                    fs.customer_key,
                    dc.city,
                    SUM(fs.revenue) as customer_revenue,
                    COUNT(fs.sale_id) as customer_transactions,
                    MIN(dd.date) as first_purchase_date,
                    MAX(dd.date) as last_purchase_date
                FROM fact_sales fs
                JOIN dim_customer dc ON fs.customer_key = dc.customer_key
                JOIN dim_date dd ON fs.date_key = dd.date_key
                GROUP BY fs.customer_key, dc.city
            )
            SELECT
                city,
                CASE
                    WHEN city IN ('Mumbai', 'Delhi', 'Bangalore') THEN 'Metro'
                    WHEN city IN ('Pune', 'Hyderabad', 'Chennai') THEN 'Tier-1'
                    ELSE 'Tier-2'
                END as city_tier,
                COUNT(*) as customer_count,
                SUM(customer_revenue) as total_revenue,
                AVG(customer_revenue) as avg_clv,
                SUM(customer_transactions) as total_transactions,
                SUM(customer_revenue) / SUM(customer_transactions) as avg_transaction_value,
                AVG(DATE_DIFF('day', first_purchase_date, last_purchase_date)) as customer_lifespan_days,
                CASE
                    WHEN AVG(customer_transactions) <= 1 THEN 'One-time'
                    WHEN AVG(customer_transactions) <= 5 THEN 'Occasional'
                    WHEN AVG(customer_transactions) <= 15 THEN 'Regular'
                    ELSE 'Loyal'
                END as purchase_frequency_segment,
                CASE
                    WHEN AVG(customer_revenue) < 1000 THEN 'Low Value'
                    WHEN AVG(customer_revenue) < 5000 THEN 'Medium Value'
                    WHEN AVG(customer_revenue) < 20000 THEN 'High Value'
                    ELSE 'Premium'
                END as value_segment
            FROM customer_agg
            GROUP BY city
            ORDER BY total_revenue DESC
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_stockout_risks():
    """Get inventory movement analysis with stockout risk indicators.

    sales_span_days is computed from real dim_date.date values rather than
    subtracting date_key integers directly (YYYYMMDD subtraction is not a
    valid day count across month/year boundaries).
    """
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            WITH sales_span AS (
                SELECT
                    fs.product_key,
                    SUM(fs.quantity) as total_sold,
                    SUM(fs.revenue) as total_revenue,
                    COUNT(DISTINCT fs.date_key) as days_sold,
                    MIN(dd.date) as first_sale_date,
                    MAX(dd.date) as last_sale_date
                FROM fact_sales fs
                JOIN dim_date dd ON fs.date_key = dd.date_key
                GROUP BY fs.product_key
            )
            SELECT
                dp.product_id,
                dp.name as product_name,
                dp.category,
                dp.price,
                ss.total_sold,
                ss.total_revenue,
                ss.days_sold,
                ss.first_sale_date,
                ss.last_sale_date,
                ss.total_sold * 1.0 / NULLIF(ss.days_sold, 0) as avg_daily_sales,
                DATE_DIFF('day', ss.first_sale_date, ss.last_sale_date) as sales_span_days,
                CASE
                    WHEN ss.total_sold * 1.0 / NULLIF(ss.days_sold, 0) > 10 THEN 'Fast Moving'
                    WHEN ss.total_sold * 1.0 / NULLIF(ss.days_sold, 0) > 2 THEN 'Medium Moving'
                    ELSE 'Slow Moving'
                END as movement_category,
                ROUND((ss.total_sold * 1.0 / NULLIF(ss.days_sold, 0)) * 30, 2) as projected_monthly_sales,
                ROUND((ss.total_sold * 1.0 / NULLIF(ss.days_sold, 0)) * 365, 2) as projected_annual_sales
            FROM sales_span ss
            JOIN dim_product dp ON dp.product_key = ss.product_key
            ORDER BY avg_daily_sales DESC
            LIMIT 20
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_inventory_turnover():
    """Inventory Turnover Ratio: units sold per unit of average stock held,
    computed from fact_inventory (actual stock snapshots) and fact_sales."""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            WITH avg_inventory AS (
                SELECT product_key, AVG(stock_level) as avg_stock_level
                FROM fact_inventory
                GROUP BY product_key
            ),
            sold AS (
                SELECT product_key, SUM(quantity) as total_units_sold
                FROM fact_sales
                GROUP BY product_key
            )
            SELECT
                dp.product_id,
                dp.name as product_name,
                dp.category,
                s.total_units_sold,
                ROUND(ai.avg_stock_level, 2) as avg_stock_level,
                ROUND(s.total_units_sold / NULLIF(ai.avg_stock_level, 0), 2) as inventory_turnover_ratio
            FROM sold s
            JOIN avg_inventory ai ON ai.product_key = s.product_key
            JOIN dim_product dp ON dp.product_key = s.product_key
            ORDER BY inventory_turnover_ratio DESC
            LIMIT 20
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_delivery_performance():
    """Average delivery time (and on-time rate) by month, from fact_shipments."""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            SELECT
                DATE_TRUNC('month', dd.date) as delivery_month,
                COUNT(*) as total_deliveries,
                ROUND(AVG(fsh.delivery_time), 2) as avg_delivery_days,
                MIN(fsh.delivery_time) as min_delivery_days,
                MAX(fsh.delivery_time) as max_delivery_days,
                ROUND(100.0 * SUM(CASE WHEN fsh.on_time_flag THEN 1 ELSE 0 END) / COUNT(*), 2) as on_time_pct
            FROM fact_shipments fsh
            JOIN dim_date dd ON dd.date_key = fsh.date_key
            GROUP BY DATE_TRUNC('month', dd.date)
            ORDER BY delivery_month DESC
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_top_product_pairs():
    """Market basket analysis: products frequently bought together.

    A 'basket' is approximated as all items a customer bought on the same
    day (fact_sales has one row per line item, not a shared order id).
    Returns co-occurrence count, confidence (P(B|A)), and lift for the
    top product pairs.
    """
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            WITH baskets AS (
                SELECT
                    (customer_key::VARCHAR || '_' || date_key::VARCHAR) as basket_id,
                    product_key
                FROM fact_sales
            ),
            basket_totals AS (
                SELECT COUNT(DISTINCT basket_id) as n FROM baskets
            ),
            product_basket_counts AS (
                SELECT product_key, COUNT(DISTINCT basket_id) as basket_count
                FROM baskets
                GROUP BY product_key
            ),
            pairs AS (
                SELECT
                    a.product_key as product_a_key,
                    b.product_key as product_b_key,
                    COUNT(DISTINCT a.basket_id) as co_occurrence_count
                FROM baskets a
                JOIN baskets b ON a.basket_id = b.basket_id AND a.product_key < b.product_key
                GROUP BY a.product_key, b.product_key
            )
            SELECT
                dpa.product_id as product_a,
                dpb.product_id as product_b,
                pairs.co_occurrence_count,
                ROUND(pairs.co_occurrence_count * 1.0 / pca.basket_count, 4) as confidence,
                ROUND(
                    (pairs.co_occurrence_count * 1.0 / pca.basket_count)
                    / (pcb.basket_count * 1.0 / bt.n),
                    4
                ) as lift
            FROM pairs
            JOIN product_basket_counts pca ON pca.product_key = pairs.product_a_key
            JOIN product_basket_counts pcb ON pcb.product_key = pairs.product_b_key
            CROSS JOIN basket_totals bt
            JOIN dim_product dpa ON dpa.product_key = pairs.product_a_key
            JOIN dim_product dpb ON dpb.product_key = pairs.product_b_key
            ORDER BY pairs.co_occurrence_count DESC, lift DESC
            LIMIT 20
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_ai_decisions():
    """Recent ML-driven decisions, from ml_reasoning_log (populated by
    MLPredictiveEngine.predict_stockout_with_explanation each time it runs).
    Returns [] if the table doesn't exist yet or has no rows logged."""
    try:
        with get_connection(read_only=True) as con:
            df = con.execute(
                """
                SELECT id, timestamp, model_name, product_id, store_id, prediction, confidence, explanation_json
                FROM ml_reasoning_log
                ORDER BY timestamp DESC
                LIMIT 20
                """
            ).fetchdf()
    except Exception:
        return []

    decisions = []
    for _, row in df.iterrows():
        try:
            explanation = json.loads(row["explanation_json"]) if row["explanation_json"] else {}
        except (TypeError, json.JSONDecodeError):
            explanation = {}

        risk_level = explanation.get("risk_level", "Unknown")
        decisions.append({
            "decision_id": f"ML-{int(row['id'])}",
            "timestamp": str(row["timestamp"]),
            "decision_type": row["model_name"],
            "entity": f"{row['product_id']} @ {row['store_id']}",
            "action": f"Recommend reorder of {int(row['prediction'])} units",
            "confidence": float(row["confidence"]),
            "impact": f"{risk_level} stockout risk",
            "status": "executed",
        })

    return decisions
