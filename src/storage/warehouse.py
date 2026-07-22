"""DuckDB warehouse utilities.

This module is intentionally small and dependency-free so the rest of the codebase
can standardize on:

- one canonical DB path (from src.config)
- safe connection lifecycle (context manager)
- explicit read-only vs write connections
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import duckdb

try:
	# Preferred: project-wide config
	from src.config import DB_PATH as _CONFIG_DB_PATH

	DB_PATH: Path = Path(_CONFIG_DB_PATH)
except Exception:
	# Fallback for running individual scripts in isolation
	DB_PATH = Path("data/warehouse/retail.duckdb")


@contextmanager
def get_connection(*, read_only: bool = False, db_path: Optional[Path] = None) -> Iterator[duckdb.DuckDBPyConnection]:
	"""Yield a DuckDB connection and always close it.

	DuckDB connections are not generally thread-safe; prefer short-lived
	connections per request/job.
	"""

	path = (db_path or DB_PATH)
	con = duckdb.connect(str(path), read_only=read_only)
	try:
		yield con
	finally:
		try:
			con.close()
		except Exception:
			# Best-effort close; avoid masking upstream exceptions
			pass


def ensure_warehouse_dirs() -> None:
	"""Ensure the parent directory for the DuckDB file exists."""

	DB_PATH.parent.mkdir(parents=True, exist_ok=True)

