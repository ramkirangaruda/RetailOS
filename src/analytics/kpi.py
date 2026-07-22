from __future__ import annotations

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
    """Get customer distribution by city with tier and value segmentation"""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            SELECT 
                dc.city,
                CASE 
                    WHEN dc.city IN ('Mumbai', 'Delhi', 'Bangalore') THEN 'Metro'
                    WHEN dc.city IN ('Pune', 'Hyderabad', 'Chennai') THEN 'Tier-1'
                    ELSE 'Tier-2'
                END as city_tier,
                COUNT(DISTINCT fs.customer_key) as customer_count,
                SUM(fs.revenue) as total_revenue,
                AVG(fs.revenue) as avg_clv,
                COUNT(fs.sale_id) as total_transactions,
                AVG(fs.revenue) as avg_transaction_value,
                (MAX(fs.date_key) - MIN(fs.date_key)) as customer_lifespan_days,
                CASE 
                    WHEN COUNT(fs.sale_id) = 1 THEN 'One-time'
                    WHEN COUNT(fs.sale_id) <= 5 THEN 'Occasional'
                    WHEN COUNT(fs.sale_id) <= 15 THEN 'Regular'
                    ELSE 'Loyal'
                END as purchase_frequency_segment,
                CASE 
                    WHEN SUM(fs.revenue) < 1000 THEN 'Low Value'
                    WHEN SUM(fs.revenue) < 5000 THEN 'Medium Value'
                    WHEN SUM(fs.revenue) < 20000 THEN 'High Value'
                    ELSE 'Premium'
                END as value_segment
            FROM fact_sales fs
            JOIN dim_customer dc ON fs.customer_key = dc.customer_key
            GROUP BY dc.city
            ORDER BY total_revenue DESC
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_stockout_risks():
    """Get inventory movement analysis with stockout risk indicators"""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            SELECT 
                dp.product_id,
                dp.name as product_name,
                dp.category,
                dp.price,
                SUM(fs.quantity) as total_sold,
                SUM(fs.revenue) as total_revenue,
                COUNT(DISTINCT fs.date_key) as days_sold,
                MIN(fs.date_key) as first_sale_date,
                MAX(fs.date_key) as last_sale_date,
                SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0) as avg_daily_sales,
                (MAX(fs.date_key) - MIN(fs.date_key)) as sales_span_days,
                CASE 
                    WHEN SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0) > 10 THEN 'Fast Moving'
                    WHEN SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0) > 2 THEN 'Medium Moving'
                    ELSE 'Slow Moving'
                END as movement_category,
                ROUND((SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0)) * 30, 2) as projected_monthly_sales,
                ROUND((SUM(fs.quantity) * 1.0 / NULLIF(COUNT(DISTINCT fs.date_key), 0)) * 365, 2) as projected_annual_sales
            FROM fact_sales fs
            JOIN dim_product dp ON fs.product_key = dp.product_key
            GROUP BY dp.product_id, dp.name, dp.category, dp.price
            ORDER BY avg_daily_sales DESC
            LIMIT 20
            """
        ).fetchdf()

        return df.to_dict(orient="records")


def get_top_product_pairs():
    """Get top product pairs for cross-selling (placeholder)"""
    # This would require market basket analysis
    # For now, return empty list
    return []


def get_ai_decisions():
    """Get AI decision feed (placeholder)"""
    # This would come from an AI decision log table
    # For now, return empty list
    return []
