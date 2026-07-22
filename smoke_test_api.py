from __future__ import annotations

import requests


def check(url: str) -> None:
    r = requests.get(url, timeout=10)
    ct = r.headers.get("content-type", "")
    print(f"{url} -> {r.status_code} ({ct})")
    r.raise_for_status()

    if "application/json" in ct:
        data = r.json()
        if isinstance(data, list):
            print(f"  JSON list len={len(data)}")
            if data and isinstance(data[0], dict):
                print(f"  keys(sample)={list(data[0].keys())[:8]}")
        elif isinstance(data, dict):
            print(f"  JSON dict keys={list(data.keys())[:12]}")
    else:
        print(r.text[:200])


def main() -> int:
    base = "http://127.0.0.1:8000"
    urls = [
        f"{base}/health",
        f"{base}/openapi.json",
        f"{base}/api/kpi/daily-revenue",
        f"{base}/api/kpi/city-sales",
        f"{base}/api/kpi/customer-distribution",
        f"{base}/api/kpi/stockout-risks",
    ]

    for u in urls:
        check(u)

    print("OK: backend smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
