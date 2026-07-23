# Data Quality Report

**Generated:** 2026-07-23 18:42:06

---

## Summary

- **Initial Rows:** 102,000
- **Final Rows:** 100,000
- **Rows Removed:** 2,000
- **Retention Rate:** 98.04%

---

## Cleaning Steps

### Step 1: Duplicate Removal
- **Duplicates Removed:** 2,000

### Step 2: Missing Value Handling
- **Null Discounts Fixed:** 0

### Step 3: Critical Field Validation
- **Rows Removed (Missing Critical Fields):** 0

### Step 4: Data Correction
- **Negative Prices Fixed:** 486

### Step 5: Quantity Validation
- **Invalid Quantities Removed:** 0

### Step 6: Temporal Validation
- **Future Timestamps Removed:** 0

### Step 7: Anomaly Detection
- **Anomalies Flagged:** 2,687
- **Note:** Anomalies are flagged but NOT removed.

---

## Detailed Statistics

```
initial_rows: 102,000
duplicates_removed: 2,000
nulls_fixed: 0
critical_rows_removed: 0
invalid_values_fixed: 486
invalid_quantity_removed: 0
future_rows_removed: 0
anomalies_flagged: 2,687
final_rows: 100,000
```
