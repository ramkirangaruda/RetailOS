-- =====================================================
-- RetailOS KPI Queries
-- Compatible with DuckDB and actual database schema
-- =====================================================

-- =====================================================
-- 1. Daily Revenue
-- =====================================================
-- Description: Total revenue generated each day with time-based analysis
-- Dependencies: fact_sales, dim_date

SELECT 
    dd.date,
    dd.year,
    dd.month,
    dd.day,
    CASE dd.is_weekend WHEN true THEN 'Weekend' ELSE 'Weekday' END as day_type,
    CASE dd.is_holiday WHEN true THEN 'Holiday' ELSE 'Regular' END as holiday_type,
    dd.festival_name,
    SUM(fs.revenue) as daily_revenue,
    COUNT(fs.sale_id) as transaction_count,
    AVG(fs.revenue) as avg_transaction_value,
    SUM(fs.quantity) as total_units_sold
FROM fact_sales fs
JOIN dim_date dd ON fs.date_key = dd.date_key
GROUP BY dd.date, dd.year, dd.month, dd.day, dd.is_weekend, dd.is_holiday, dd.festival_name
ORDER BY dd.date DESC;

-- =====================================================
-- 2. Monthly Revenue
-- =====================================================
-- Description: Total revenue generated each month with growth analysis
-- Dependencies: fact_sales, dim_date

SELECT 
    dd.year,
    dd.month,
    CASE dd.month 
        WHEN 1 THEN 'January'
        WHEN 2 THEN 'February'
        WHEN 3 THEN 'March'
        WHEN 4 THEN 'April'
        WHEN 5 THEN 'May'
        WHEN 6 THEN 'June'
        WHEN 7 THEN 'July'
        WHEN 8 THEN 'August'
        WHEN 9 THEN 'September'
        WHEN 10 THEN 'October'
        WHEN 11 THEN 'November'
        WHEN 12 THEN 'December'
    END as month_name,
    SUM(fs.revenue) as monthly_revenue,
    COUNT(fs.sale_id) as transaction_count,
    AVG(fs.revenue) as avg_transaction_value,
    SUM(fs.quantity) as total_units_sold,
    LAG(SUM(fs.revenue)) OVER (ORDER BY dd.year, dd.month) as prev_month_revenue,
    ROUND(
        (SUM(fs.revenue) - LAG(SUM(fs.revenue)) OVER (ORDER BY dd.year, dd.month)) * 100.0 / 
        NULLIF(LAG(SUM(fs.revenue)) OVER (ORDER BY dd.year, dd.month), 0), 
        2
    ) as revenue_growth_pct
FROM fact_sales fs
JOIN dim_date dd ON fs.date_key = dd.date_key
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;

-- =====================================================
-- 3. City-wise Sales
-- =====================================================
-- Description: Sales performance by city with regional analysis
-- Dependencies: fact_sales, dim_store

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
ORDER BY total_revenue DESC;

-- =====================================================
-- 4. Top 10 Selling Products (by revenue)
-- =====================================================
-- Description: Best performing products by revenue with ranking
-- Dependencies: fact_sales, dim_product

SELECT 
    dp.product_id,
    dp.name as product_name,
    dp.category,
    dp.brand,
    SUM(fs.quantity) as total_quantity_sold,
    SUM(fs.revenue) as total_revenue,
    COUNT(fs.sale_id) as transaction_count,
    AVG(fs.revenue) as avg_revenue_per_transaction,
    AVG(dp.price) as avg_product_price,
    ROUND(SUM(fs.revenue) * 100.0 / SUM(SUM(fs.revenue)) OVER (), 2) as revenue_share_pct,
    ROW_NUMBER() OVER (ORDER BY SUM(fs.revenue) DESC) as revenue_rank
FROM fact_sales fs
JOIN dim_product dp ON fs.product_key = dp.product_key
GROUP BY dp.product_id, dp.name, dp.category, dp.brand, dp.price
ORDER BY total_revenue DESC
LIMIT 10;

-- =====================================================
-- 5. Product Sales Velocity (movement category)
-- =====================================================
-- Description: Sales-side movement classification (fast/medium/slow moving).
-- NOTE: this is a sell-through proxy, NOT the inventory turnover ratio below
-- -- it never touches fact_inventory. sales_span_days/first/last_sale_date
-- come from dim_date.date, not from subtracting date_key integers directly
-- (date_key is YYYYMMDD, e.g. 20240301 - 20240228 = 73, not 2 days).
-- Dependencies: fact_sales, dim_product, dim_date

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
ORDER BY avg_daily_sales DESC;

-- =====================================================
-- 5b. Inventory Turnover Ratio
-- =====================================================
-- Description: units sold per unit of average stock held, using actual
-- daily stock snapshots in fact_inventory (populated by
-- src/storage/populate_inventory.py).
-- Dependencies: fact_sales, fact_inventory, dim_product

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
ORDER BY inventory_turnover_ratio DESC;

-- =====================================================
-- 6. Average Delivery Time
-- =====================================================
-- Description: Real delivery performance from fact_shipments (populated by
-- src/storage/populate_shipments.py from shipments.csv's ship_date/
-- delivery_date). on_time_flag uses a 5-day threshold (the median observed
-- delivery_time in this dataset; the source has no explicit SLA).
-- Dependencies: fact_shipments, dim_date

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
ORDER BY delivery_month DESC;

-- =====================================================
-- 7. Seasonal Demand Trends (month-wise)
-- =====================================================
-- Description: Monthly sales patterns with seasonal analysis
-- Dependencies: fact_sales, dim_date

SELECT 
    dd.year,
    dd.month,
    CASE dd.month 
        WHEN 1 THEN 'January'
        WHEN 2 THEN 'February'
        WHEN 3 THEN 'March'
        WHEN 4 THEN 'April'
        WHEN 5 THEN 'May'
        WHEN 6 THEN 'June'
        WHEN 7 THEN 'July'
        WHEN 8 THEN 'August'
        WHEN 9 THEN 'September'
        WHEN 10 THEN 'October'
        WHEN 11 THEN 'November'
        WHEN 12 THEN 'December'
    END as month_name,
    CASE 
        WHEN dd.month IN (12, 1, 2) THEN 'Winter'
        WHEN dd.month IN (3, 4, 5) THEN 'Spring'
        WHEN dd.month IN (6, 7, 8) THEN 'Summer'
        ELSE 'Monsoon'
    END as season,
    SUM(fs.revenue) as monthly_revenue,
    COUNT(fs.sale_id) as transaction_count,
    AVG(fs.revenue) as avg_transaction_value,
    SUM(fs.quantity) as total_units_sold,
    ROUND(SUM(fs.revenue) * 100.0 / SUM(SUM(fs.revenue)) OVER (), 2) as revenue_share_pct,
    LAG(SUM(fs.revenue)) OVER (ORDER BY dd.year, dd.month) as prev_month_revenue,
    ROUND(
        (SUM(fs.revenue) - LAG(SUM(fs.revenue)) OVER (ORDER BY dd.year, dd.month)) * 100.0 / 
        NULLIF(LAG(SUM(fs.revenue)) OVER (ORDER BY dd.year, dd.month), 0), 
        2
    ) as month_over_month_growth_pct
FROM fact_sales fs
JOIN dim_date dd ON fs.date_key = dd.date_key
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;

-- =====================================================
-- 8. New vs Returning Customers
-- =====================================================
-- Description: Customer acquisition and retention analysis
-- Dependencies: fact_sales, dim_customer, dim_date

SELECT 
    dd.date,
    COUNT(DISTINCT fs.customer_key) as total_customers,
    COUNT(DISTINCT CASE WHEN fs.date_key = (
        SELECT MIN(fs2.date_key) 
        FROM fact_sales fs2 
        WHERE fs2.customer_key = fs.customer_key
    ) THEN fs.customer_key END) as new_customers,
    COUNT(DISTINCT CASE WHEN fs.date_key > (
        SELECT MIN(fs2.date_key) 
        FROM fact_sales fs2 
        WHERE fs2.customer_key = fs.customer_key
    ) THEN fs.customer_key END) as returning_customers,
    SUM(fs.revenue) as total_revenue,
    ROUND(COUNT(DISTINCT CASE WHEN fs.date_key = (
        SELECT MIN(fs2.date_key) 
        FROM fact_sales fs2 
        WHERE fs2.customer_key = fs.customer_key
    ) THEN fs.customer_key END) * 100.0 / NULLIF(COUNT(DISTINCT fs.customer_key), 0), 2) as new_customer_pct,
    ROUND(COUNT(DISTINCT CASE WHEN fs.date_key > (
        SELECT MIN(fs2.date_key) 
        FROM fact_sales fs2 
        WHERE fs2.customer_key = fs.customer_key
    ) THEN fs.customer_key END) * 100.0 / NULLIF(COUNT(DISTINCT fs.customer_key), 0), 2) as returning_customer_pct
FROM fact_sales fs
JOIN dim_date dd ON fs.date_key = dd.date_key
GROUP BY dd.date
ORDER BY dd.date DESC;

-- =====================================================
-- 9. Customer Lifetime Value (CLV)
-- =====================================================
-- Description: avg_clv is the average per-customer lifetime revenue
-- (aggregated per customer first, then averaged within the city) rather
-- than the average transaction value. customer_lifespan_days comes from
-- real dim_date.date values, not date_key integer subtraction.
-- Dependencies: fact_sales, dim_customer, dim_date

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
ORDER BY total_revenue DESC;

-- =====================================================
-- 10. Market Basket Analysis (frequently bought together)
-- =====================================================
-- Description: fact_sales has one row per line item, not a shared order id,
-- so a 'basket' is approximated as everything a customer bought on the same
-- day. Returns co-occurrence count, confidence (P(B|A)), and lift per pair.
-- Dependencies: fact_sales, dim_product

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
LIMIT 20;

-- =====================================================
-- Additional Utility Queries
-- =====================================================

-- Quick Summary Dashboard
SELECT 
    'Total Revenue' as metric,
    SUM(revenue) as value,
    '₹' || ROUND(SUM(revenue), 2) as formatted_value
FROM fact_sales
UNION ALL
SELECT 
    'Total Transactions' as metric,
    COUNT(sale_id) as value,
    CAST(COUNT(sale_id) AS VARCHAR) as formatted_value
FROM fact_sales
UNION ALL
SELECT 
    'Total Customers' as metric,
    COUNT(DISTINCT customer_key) as value,
    CAST(COUNT(DISTINCT customer_key) AS VARCHAR) as formatted_value
FROM fact_sales
UNION ALL
SELECT 
    'Total Products' as metric,
    COUNT(DISTINCT product_key) as value,
    CAST(COUNT(DISTINCT product_key) AS VARCHAR) as formatted_value
FROM fact_sales
UNION ALL
SELECT 
    'Total Stores' as metric,
    COUNT(DISTINCT store_key) as value,
    CAST(COUNT(DISTINCT store_key) AS VARCHAR) as formatted_value
FROM fact_sales;
