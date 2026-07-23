import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


@dataclass
class TableSchema:
    """Schema definition for a logical table."""

    name: str
    required_columns: List[str]
    optional_columns: List[str] = field(default_factory=list)

    @property
    def all_known_columns(self) -> List[str]:
        return self.required_columns + self.optional_columns


class SchemaRegistry:
    """Very simple in-memory schema registry."""

    def __init__(self, schemas: List[TableSchema]) -> None:
        self._schemas: Dict[str, TableSchema] = {s.name: s for s in schemas}

    def get(self, table_name: str) -> Optional[TableSchema]:
        return self._schemas.get(table_name)


@dataclass
class IngestionConfig:
    raw_dir: Path = Path("data/raw")
    quarantine_dir: Path = Path("data/quarantine")
    output_dir: Path = Path("data/raw")  # Parquet output (can be different if desired)
    max_retries: int = 3
    base_backoff_seconds: float = 1.0  # exponential backoff base


class BatchIngestionPipeline:
    """
    Batch ingestion pipeline that:
    - Reads CSV files from data/raw/
    - Validates schema against a registry
    - Handles schema evolution (new columns = log drift, missing required = quarantine)
    - Auto-retries on read failures
    - Quarantines invalid records with reason
    - Saves valid records as Parquet with timestamp
    - Logs every step with row counts
    """

    def __init__(self, schema_registry: SchemaRegistry, config: Optional[IngestionConfig] = None) -> None:
        self.schema_registry = schema_registry
        self.config = config or IngestionConfig()
        self.config.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Public API
    # -----------------------------

    def run_for_table(self, table_name: str, csv_filename: str) -> Dict[str, int]:
        """
        Run ingestion for a single logical table / csv file.

        Parameters
        ----------
        table_name : str
            Logical name used to look up schema.
        csv_filename : str
            File name under raw_dir, e.g. 'customers.csv'.

        Returns
        -------
        dict with 'valid_rows' and 'quarantined_rows' counts (both 0 if the
        file could not be read after retries).
        """
        logger.info("Starting ingestion for table=%s, file=%s", table_name, csv_filename)
        schema = self.schema_registry.get(table_name)
        if not schema:
            raise ValueError(f"No schema registered for table '{table_name}'")

        csv_path = self.config.raw_dir / csv_filename

        df = self._read_with_retries(csv_path)
        if df is None:
            logger.error("Failed to read file after retries: %s", csv_path)
            return {"valid_rows": 0, "quarantined_rows": 0}

        logger.info("Read CSV '%s' with %d rows and %d columns", csv_path, len(df), len(df.columns))

        valid_df, quarantine_df = self._validate_and_split(df, schema)

        if not quarantine_df.empty:
            self._write_quarantine(table_name, quarantine_df)

        if not valid_df.empty:
            self._write_parquet(table_name, valid_df)

        logger.info(
            "Completed ingestion for table=%s: valid_rows=%d, quarantined_rows=%d",
            table_name,
            len(valid_df),
            len(quarantine_df),
        )

        return {"valid_rows": len(valid_df), "quarantined_rows": len(quarantine_df)}

    # -----------------------------
    # Internal helpers
    # -----------------------------

    def _read_with_retries(self, path: Path) -> Optional[pd.DataFrame]:
        attempt = 0
        while attempt < self.config.max_retries:
            try:
                logger.info("Reading CSV (attempt %d/%d): %s", attempt + 1, self.config.max_retries, path)
                df = pd.read_csv(path)
                return df
            except Exception as exc:  # noqa: BLE001
                attempt += 1
                logger.warning("Failed to read CSV '%s' on attempt %d: %s", path, attempt, exc)
                if attempt >= self.config.max_retries:
                    break
                backoff = self.config.base_backoff_seconds * (2 ** (attempt - 1))
                logger.info("Backing off for %.2f seconds before retry", backoff)
                time.sleep(backoff)
        return None

    def _validate_and_split(self, df: pd.DataFrame, schema: TableSchema) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Validate dataframe against schema and split into valid and quarantined records.

        - Rows missing any required column values => quarantine with reason.
        - Extra columns (unknown) => logged as schema drift but kept.
        """
        incoming_cols = set(df.columns.tolist())
        required = set(schema.required_columns)
        optional = set(schema.optional_columns)
        known = required | optional

        missing_required_cols = required - incoming_cols
        new_cols = incoming_cols - known

        if missing_required_cols:
            logger.warning(
                "Missing required columns for table '%s': %s",
                schema.name,
                ", ".join(sorted(missing_required_cols)),
            )

        if new_cols:
            logger.info(
                "Schema drift detected for table '%s' - new columns: %s",
                schema.name,
                ", ".join(sorted(new_cols)),
            )

        # Quarantine rows missing required values
        quarantine_mask = pd.Series(False, index=df.index)
        reasons: List[str] = []

        for col in sorted(required):
            if col not in df.columns:
                # Entire column missing: all rows quarantined for this reason
                reason = f"missing_required_column:{col}"
                logger.info("Quarantining all rows due to missing column '%s'", col)
                if quarantine_mask.any():
                    # For rows already quarantined for some other column, append reason
                    pass
                quarantine_mask |= True
                # Build per-row reasons when exporting
                reasons.append(reason)
            else:
                missing_vals = df[col].isna()
                if missing_vals.any():
                    logger.info(
                        "Column '%s' has %d rows with missing values; quarantining those rows",
                        col,
                        int(missing_vals.sum()),
                    )
                    quarantine_mask |= missing_vals

        if quarantine_mask.any():
            logger.info("Total rows to quarantine due to validation: %d", int(quarantine_mask.sum()))

        quarantine_df = df[quarantine_mask].copy()
        valid_df = df[~quarantine_mask].copy()

        # Attach a simple reason column. If multiple issues, we can store a semicolon-separated list.
        if not quarantine_df.empty:
            quarantine_reasons: List[str] = []
            for idx, row in quarantine_df.iterrows():
                row_reasons: List[str] = []
                for col in sorted(required):
                    if col not in df.columns:
                        row_reasons.append(f"missing_required_column:{col}")
                    else:
                        if pd.isna(row[col]):
                            row_reasons.append(f"missing_required_value:{col}")
                quarantine_reasons.append(";".join(sorted(set(row_reasons))) or "unknown_reason")
            quarantine_df["quarantine_reason"] = quarantine_reasons

        logger.info(
            "Validation complete for table='%s': valid_rows=%d, quarantined_rows=%d",
            schema.name,
            len(valid_df),
            len(quarantine_df),
        )

        return valid_df, quarantine_df

    def _write_quarantine(self, table_name: str, quarantine_df: pd.DataFrame) -> None:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        out_path = self.config.quarantine_dir / f"{table_name}_quarantine_{ts}.csv"
        logger.info(
            "Writing %d quarantined rows for table='%s' to '%s'",
            len(quarantine_df),
            table_name,
            out_path,
        )
        quarantine_df.to_csv(out_path, index=False)

    def _write_parquet(self, table_name: str, valid_df: pd.DataFrame) -> None:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        out_path = self.config.output_dir / f"{table_name}_{ts}.parquet"
        logger.info(
            "Writing %d valid rows for table='%s' to Parquet '%s'",
            len(valid_df),
            table_name,
            out_path,
        )
        valid_df.to_parquet(out_path, index=False)


# Single source of truth for which (table_name, csv_filename) pairs the
# batch pipeline ingests. Reused by __main__ below and by batch_scheduler.py
# so both stay in sync.
TABLE_CSV_PAIRS: List[Tuple[str, str]] = [
    ("customers", "customers.csv"),
    ("products", "products.csv"),
    ("stores", "stores.csv"),
    ("inventory", "inventory.csv"),
    ("transactions", "transactions.csv"),
    ("shipments", "shipments.csv"),
    ("web_clickstream", "web_clickstream.csv"),
]


def default_schema_registry() -> SchemaRegistry:
    """
    Convenience factory for common retail schemas based on the existing CSVs.

    Adjust required / optional columns as needed for your project.
    """
    # Note: we do not know the exact column layouts from here, so treat all as optional.
    # You should revise these lists based on your actual CSV headers.
    schemas = [TableSchema(name=name, required_columns=[], optional_columns=[]) for name, _ in TABLE_CSV_PAIRS]
    return SchemaRegistry(schemas)


def run_all(pipeline: "BatchIngestionPipeline") -> Dict[str, int]:
    """Run ingestion for every table in TABLE_CSV_PAIRS.

    Returns aggregated {'total_rows', 'quarantined_rows'} across all tables.
    """
    total_rows = 0
    quarantined_rows = 0
    for table_name, csv_filename in TABLE_CSV_PAIRS:
        result = pipeline.run_for_table(table_name, csv_filename)
        total_rows += result["valid_rows"]
        quarantined_rows += result["quarantined_rows"]
    return {"total_rows": total_rows, "quarantined_rows": quarantined_rows}


if __name__ == "__main__":
    registry = default_schema_registry()
    pipeline = BatchIngestionPipeline(registry)
    run_all(pipeline)


