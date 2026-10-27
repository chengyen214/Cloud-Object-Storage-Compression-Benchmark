
from pathlib import Path
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json

import requests

# =========================
# 路徑與資料集設定
# =========================
OUT_DIR = Path("dataset/json")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST = Path("dataset/json_manifest.csv")

SOURCE_URL = "https://data.gharchive.org/2025-01-01-15.json.gz"

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}

# =========================
# JSON 資料集規劃
# =========================
DATASET_PLAN = [
    {
        "type": "small",
        "type_zh": "小型 JSON",
        "files": 40,
        "min_events": 100,
        "max_events": 300,
    },
    {
        "type": "medium",
        "type_zh": "中型 JSON",
        "files": 40,
        "min_events": 500,
        "max_events": 1000,
    },
    {
        "type": "large",
        "type_zh": "大型 JSON",
        "files": 20,
        "min_events": 1500,
        "max_events": 3000,
    },
]

# 使用每種檔案的目標事件數
# 小型 200 筆、中型 750 筆、大型 2,000 筆
TARGET_EVENTS = {
    "small": 200,
    "medium": 750,
    "large": 2000,
}


def load_events():
    """下載 GH Archive，解析 NDJSON 事件。"""
    print("下載 GH Archive 公開事件資料...")
    print("來源：", SOURCE_URL)

    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=180,
    )
    response.raise_for_status()

    print("下載完成，正在解壓縮與解析...")

    raw = gzip.decompress(response.content)
    events = []

    for line in raw.splitlines():
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(event, dict):
            events.append(event)

    print(f"有效事件數：{len(events):,}")
    return events


def build_file_specs():
    """依照規劃建立每個檔案的事件數設定。"""
    specs = []

    for group in DATASET_PLAN:
        target = TARGET_EVENTS[group["type"]]

        if not group["min_events"] <= target <= group["max_events"]:
            raise ValueError(
                f"{group['type_zh']}的目標事件數不在允許範圍內"
            )

        for _ in range(group["files"]):
            specs.append({
                "type": group["type"],
                "type_zh": group["type_zh"],
                "event_count": target,
            })

    return specs


def main():
    specs = build_file_specs()
    required_events = sum(
        spec["event_count"] for spec in specs
    )

    print("\n========== 資料集規劃 ==========")
    for group in DATASET_PLAN:
        target = TARGET_EVENTS[group["type"]]
        print(
            f"{group['type_zh']}: "
            f"{group['files']} 個檔案，"
            f"每檔 {target:,} 筆事件"
        )

    print(f"預計檔案總數：{len(specs)}")
    print(f"需要事件總數：{required_events:,}")

    events = load_events()

    if len(events) < required_events:
        raise RuntimeError(
            f"事件不足：需要 {required_events:,} 筆，"
            f"但來源只有 {len(events):,} 筆。\n"
            "請改用多個 GH Archive 小時檔案合併資料後再執行。"
        )

    rows = []
    event_offset = 0
    timestamp = datetime.now(timezone.utc).isoformat()

    # =========================
    # 依規模輸出 JSON 檔案
    # =========================
    for index, spec in enumerate(specs, start=1):
        count = spec["event_count"]

        batch = events[event_offset:event_offset + count]
        event_offset += count

        filename = f"gharchive_{index:03d}.json"
        path = OUT_DIR / filename

        content = (
            json.dumps(
                batch,
                ensure_ascii=False,
                indent=2,
            ) + "\n"
        ).encode("utf-8")

        path.write_bytes(content)

        rows.append({
            "filename": filename,
            "dataset_type": spec["type"],
            "dataset_type_zh": spec["type_zh"],
            "format": "JSON array",
            "event_count": len(batch),
            "size_bytes": len(content),
            "size_KiB": round(len(content) / 1024, 2),
            "size_MiB": round(len(content) / (1024 ** 2), 4),
            "sha256": hashlib.sha256(content).hexdigest(),
            "source": SOURCE_URL,
            "license_or_terms":
                "GH Archive; verify applicable terms before redistribution",
            "downloaded_at_utc": timestamp,
        })

        print(
            f"[{index:03d}/100] {filename} | "
            f"{spec['type_zh']} | "
            f"{len(batch):,} 筆事件 | "
            f"{len(content):,} bytes"
        )

    # =========================
    # 輸出 Manifest
    # =========================
    fields = [
        "filename",
        "dataset_type",
        "dataset_type_zh",
        "format",
        "event_count",
        "size_bytes",
        "size_KiB",
        "size_MiB",
        "sha256",
        "source",
        "license_or_terms",
        "downloaded_at_utc",
    ]

    with MANIFEST.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # =========================
    # 摘要
    # =========================
    print("\n========== JSON 資料集完成 ==========")
    print(f"檔案總數：{len(rows)}")
    print(f"事件總數：{event_offset:,}")
    print(
        f"總大小："
        f"{sum(row['size_bytes'] for row in rows) / 1024**2:.2f} MiB"
    )

    print("\n各類檔案數量：")
    for group in DATASET_PLAN:
        count = sum(
            row["dataset_type"] == group["type"]
            for row in rows
        )
        print(f"{group['type_zh']}：{count} 個")

    print(f"\n輸出資料夾：{OUT_DIR.resolve()}")
    print(f"Manifest：{MANIFEST.resolve()}")


if __name__ == "__main__":
    main()
