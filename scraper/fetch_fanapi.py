"""
Pulls all data from the free Elden Ring Fan API (no key required).
Run once: python scraper/fetch_fanapi.py
"""

import httpx
import json
import time
from pathlib import Path

BASE = "https://eldenring.fanapis.com/api"
OUT_FILE = Path("data/raw/fanapi.json")

ENDPOINTS = [
    "bosses",
    "weapons",
    "armors",
    "items",
    "creatures",
    "locations",
    "npcs",
    "classes",
    "ammos",
    "ashes",
    "shields",
    "sorceries",
    "incantations",
    "talismans",
    "spirits",
]

PAGE_SIZE = 100


def fetch_all(client: httpx.Client, endpoint: str) -> list[dict]:
    records = []
    page = 0
    while True:
        url = f"{BASE}/{endpoint}?limit={PAGE_SIZE}&page={page}"
        try:
            resp = client.get(url)
            data = resp.json()
        except Exception as e:
            print(f"    ERROR page {page}: {e}")
            break

        if not data.get("success"):
            break

        batch = data.get("data", [])
        if not batch:
            break

        records.extend(batch)
        total = data.get("total", 0)
        print(f"    {endpoint}: {len(records)}/{total}")

        if len(records) >= total:
            break
        page += 1
        time.sleep(0.3)

    return records


def fetch() -> dict:
    all_data = {}
    with httpx.Client(follow_redirects=True, timeout=15) as client:
        for endpoint in ENDPOINTS:
            print(f"  Fetching {endpoint} ...")
            records = fetch_all(client, endpoint)
            all_data[endpoint] = records
            print(f"  Done: {len(records)} records")
    return all_data


if __name__ == "__main__":
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print("Fetching Elden Ring Fan API ...")
    data = fetch()
    OUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in data.values())
    print(f"\nDone. {total} total records saved to {OUT_FILE}")
