import streamlit as st
import duckdb
import json
import pandas as pd

DB_PATH = "data/warehouse/retail.duckdb"

st.set_page_config(page_title="Schema Governance", layout="wide")

st.title("🛡 Adaptive Schema Governance")

con = duckdb.connect(DB_PATH)

# =====================================================
# Pending Approval Requests
# =====================================================
st.header("📌 Pending Schema Decisions")

pending = con.execute("""
SELECT queue_id, table_name, action, reason, decision_json, created_at
FROM schema_approval_queue
WHERE status = 'pending'
ORDER BY created_at DESC
""").fetchdf()

if pending.empty:
    st.success("No pending schema approvals.")
else:
    for _, row in pending.iterrows():
        with st.expander(f"Queue ID {row['queue_id']} — {row['table_name']}"):

            st.write("**Action Proposed:**", row["action"])
            st.write("**Reason:**", row["reason"])
            st.write("**Detected At:**", row["created_at"])

            decision = json.loads(row["decision_json"])

            if "changes" in decision:
                df_changes = pd.DataFrame(decision["changes"])
                st.dataframe(df_changes)

            col1, col2 = st.columns(2)

            # Approve
            if col1.button(f"✅ Approve {row['queue_id']}"):
                con.execute("""
                UPDATE schema_approval_queue
                SET status = 'approved'
                WHERE queue_id = ?
                """, [row["queue_id"]])

                # Scoped by table_name + status=action so approving one
                # queue entry doesn't also flip unrelated pending changes
                # on other tables that happen to share the same action
                # label (e.g. two different tables both with
                # status='manual_review'). There's no shared batch id
                # between schema_change_log and schema_approval_queue, so
                # this is still an approximation if the same table has
                # multiple pending 'manual_review' batches at once.
                con.execute("""
                UPDATE schema_change_log
                SET status = 'approved',
                    approved_at = CURRENT_TIMESTAMP,
                    approved_by = 'admin'
                WHERE status = ? AND table_name = ?
                """, [row["action"], row["table_name"]])

                st.success("Approved successfully.")
                st.rerun()

            # Reject
            if col2.button(f"❌ Reject {row['queue_id']}"):
                con.execute("""
                UPDATE schema_approval_queue
                SET status = 'rejected'
                WHERE queue_id = ?
                """, [row["queue_id"]])

                con.execute("""
                UPDATE schema_change_log
                SET status = 'rejected',
                    approved_at = CURRENT_TIMESTAMP,
                    approved_by = 'admin'
                WHERE status = ? AND table_name = ?
                """, [row["action"], row["table_name"]])

                st.warning("Rejected successfully.")
                st.rerun()

# =====================================================
# Schema Change History
# =====================================================
st.header("📜 Schema Change History")

history = con.execute("""
SELECT change_id, table_name, change_type, column_name,
       confidence_score, status, detected_at
FROM schema_change_log
ORDER BY detected_at DESC
""").fetchdf()

st.dataframe(history)

con.close()
