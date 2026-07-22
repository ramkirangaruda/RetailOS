"""Compatibility entrypoint to build the DuckDB warehouse.

The root README references `python src/storage/warehouse_builder.py`.
The actual implementation lives in `src/transformation/build_schema.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:

    # When executed as `python src/storage/warehouse_builder.py`, Python sets
    # sys.path[0] to `src/storage`, so `import src...` won't resolve unless we
    # add the repo root.
    repo_root = Path(__file__).resolve().parents[2]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    from src.transformation.build_schema import build_star_schema

    build_star_schema()


if __name__ == "__main__":
    main()
