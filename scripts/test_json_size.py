
from pathlib import Path
import csv
import json
import statistics

# =========================
# 設定
# =========================
JSON_DIR = Path("dataset/json")
REPORT_CSV = Path("dataset/json_size_report.csv")

# 大小區間，單位為 MiB
SIZE_RANGES = [
    ("< 0.1 MiB", 0, 0.1 * 1024 * 1024),
    ("0.1–0.5 MiB", 0.1 * 1024 * 1024, 0.5 * 1024 * 1024),
    ("0.5–1 MiB", 0.5 * 1024 * 1024, 1 * 1024 * 1024),
    ("1–2 MiB", 1 * 1024 * 1024, 2 * 1024 * 1024),
    (">= 2 MiB", 2 * 1024 * 1024, float("inf")),
]


def main():
    files = sorted(JSON_DIR.glob("gharchive_*.json"))

    if not files:
        print(f"找不到 JSON 檔案：{JSON_DIR.resolve()}")
        print("請先執行 download_gharchive_json.py")
        return

    records = []

    for path in files:
        size = path.stat().st_size
        event_count = ""
        valid_json = False
        error_message = ""

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            valid_json = isinstance(data, list)
            if valid_json:
                event_count = len(data)
            else:
                error_message = "JSON 根元素不是陣列"

        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            error_message = str(exc)

        records.append({
            "filename": path.name,
            "size_bytes": size,
            "size_KiB": round(size / 1024, 2),
            "size_MiB": round(size / (1024 * 1024), 4),
            "event_count": event_count,
            "valid_json_array": valid_json,
            "error": error_message,
        })

    sizes = [r["size_bytes"] for r in records]
    total_bytes = sum(sizes)

    print("\n========== JSON 大小分布 ==========")
    print(f"檔案數量：{len(records)}")
    print(f"總大小：{total_bytes:,} bytes ({total_bytes / 1024**2:.2f} MiB)")
    print(f"平均大小：{statistics.mean(sizes) / 1024:.2f} KiB")
    print(f"中位數：{statistics.median(sizes) / 1024:.2f} KiB")
    print(f"最小值：{min(sizes) / 1024:.2f} KiB")
    print(f"最大值：{max(sizes) / 1024:.2f} KiB")

    if len(sizes) > 1:
        print(
            f"標準差："
            f"{statistics.stdev(sizes) / 1024:.2f} KiB"
        )

    print("\n---------- 大小區間 ----------")
    for label, lower, upper in SIZE_RANGES:
        count = sum(
            1 for size in sizes
            if lower <= size < upper
        )
        percentage = count / len(sizes) * 100
        print(f"{label:15s} {count:3d} 個 ({percentage:.1f}%)")

    print("\n---------- 最小的 5 個檔案 ----------")
    for r in sorted(records, key=lambda x: x["size_bytes"])[:5]:
        print(
            f"{r['filename']:25s} "
            f"{r['size_bytes']:>10,} bytes"
        )

    print("\n---------- 最大的 5 個檔案 ----------")
    for r in sorted(
        records,
        key=lambda x: x["size_bytes"],
        reverse=True,
    )[:5]:
        print(
            f"{r['filename']:25s} "
            f"{r['size_bytes']:>10,} bytes"
        )

    invalid = [r for r in records if not r["valid_json_array"]]
    print(f"\nJSON 格式檢查：{len(records) - len(invalid)}/{len(records)} 通過")

    if invalid:
        print("以下檔案格式有問題：")
        for r in invalid:
            print(f"- {r['filename']}: {r['error']}")

    fields = [
        "filename",
        "size_bytes",
        "size_KiB",
        "size_MiB",
        "event_count",
        "valid_json_array",
        "error",
    ]

    with REPORT_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    print(f"\n詳細報告：{REPORT_CSV.resolve()}")


if __name__ == "__main__":
    main()
