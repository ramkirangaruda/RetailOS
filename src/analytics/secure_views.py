"""Row/column-level queries against the RBAC views from
src/storage/access_control.py. Unlike src/analytics/kpi.py (pure
aggregates, no PII), these expose masked or full customer/financial detail
and are only reachable through role-gated API routes (see src/api/server.py
and src/api/auth.py)."""

from __future__ import annotations

import numpy as np

from src.storage.warehouse import get_connection


def get_analyst_sales(limit: int = 100):
    """Sales with PII masked (phone/email), no cost/profit data."""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            SELECT sale_id, date_key, product_key, store_key, quantity, revenue,
                   phone_masked, email_masked, customer_city
            FROM analyst_sales
            ORDER BY date_key DESC
            LIMIT ?
            """,
            [limit],
        ).fetchdf()
        return df.to_dict(orient="records")


def get_store_manager_sales(store_id: str | None = None, limit: int = 100):
    """Sales with PII masked, scoped to a single store when store_id is
    given (a store_manager's assigned store - see src/api/auth.py). If
    store_id is None (e.g. a finance/admin caller with no store
    assignment probing this route), returns unfiltered results."""
    query = """
        SELECT sm.sale_id, sm.date_key, sm.product_key, sm.store_key,
               ds.store_id, ds.store_name,
               sm.quantity, sm.revenue, sm.phone_masked, sm.email_masked, sm.customer_city
        FROM store_manager_sales sm
        JOIN dim_store ds ON sm.store_key = ds.store_key
    """
    params: list = []
    if store_id:
        query += " WHERE ds.store_id = ?"
        params.append(store_id)
    query += " ORDER BY sm.date_key DESC LIMIT ?"
    params.append(limit)

    with get_connection(read_only=True) as con:
        df = con.execute(query, params).fetchdf()
        return df.to_dict(orient="records")


def get_finance_sales(limit: int = 100):
    """Full sales detail: unmasked customer PII and per-line profit."""
    with get_connection(read_only=True) as con:
        df = con.execute(
            """
            SELECT sale_id, date_key, product_key, store_key, quantity, revenue,
                   customer_name, email, phone, customer_city,
                   product_name, product_category, product_price, profit
            FROM finance_sales
            ORDER BY date_key DESC
            LIMIT ?
            """,
            [limit],
        ).fetchdf()
        return df.to_dict(orient="records")


def get_admin_summary():
    """System-wide row counts and revenue summary across all core tables.

    admin_all UNIONs per-table rows where some columns are always NULL
    (e.g. dim_customer has no min/max date_key) - DuckDB/pandas represent
    those as NaN, which the JSON encoder rejects outright, so they're
    swapped for None here.
    """
    with get_connection(read_only=True) as con:
        df = con.execute("SELECT * FROM admin_all").fetchdf()
        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")
