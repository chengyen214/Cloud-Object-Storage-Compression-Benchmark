from pathlib import Path
import csv
import hashlib
from collections import Counter

# =====================================================
# 設定
# =====================================================
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "dataset" / "csv"
MANIFEST_FILE = BASE_DIR / "dataset" / "dataset_manifest.csv"

REPORT_FILE = BASE_DIR / "dataset" / "csv_quality_report.csv"
SUMMARY_FILE = BASE_DIR / "dataset" / "csv_quality_summary.txt"

EXPECTED_FILES = 100


def sha256_file(path):
    """計算檔案的 SHA-256。"""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_csv(path):
    """檢查 CSV 是否可讀取，並統計資料列與欄位。"""
    result = {
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "data_rows": 0,
        "column_count": 0,
        "readable": False,
        "empty_file": False,
        "header_valid": False,
        "sha256": "",
        "error": "",
    }

    if result["size_bytes"] == 0:
        result["empty_file"] = True
        result["error"] = "Empty file"
        return result

    try:
        result["sha256"] = sha256_file(path)

        # utf-8-sig 可以處理帶有 BOM 的 UTF-8 CSV
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.reader(file, strict=True)

            try:
                header = next(reader)
            except StopIteration:
                result["empty_file"] = True
                result["error"] = "No CSV content"
                return result

            if not header or not any(
                value.strip() for value in header
            ):
                result["error"] = "Invalid header"
                return result

            result["header_valid"] = True
            result["column_count"] = len(header)

            rows = 0

            for row in reader:
                if row and any(value.strip() for value in row):
                    rows += 1

            result["data_rows"] = rows
            result["readable"] = True

            if rows == 0:
                result["error"] = "No data rows"

    except (UnicodeDecodeError, csv.Error, OSError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def load_manifest():
    """讀取 Manifest，並依檔名建立索引。"""
    if not MANIFEST_FILE.exists():
        print(f"警告：找不到 Manifest：{MANIFEST_FILE}")
        return {}

    with MANIFEST_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    manifest = {}

    for row in rows:
        filename = (row.get("filename") or "").strip()

        if filename:
            manifest.setdefault(filename, []).append(row)

    return manifest


def main():
    print("========== CSV 資料集品質檢查 ==========")

    if not DATA_DIR.exists():
        print(f"找不到資料夾：{DATA_DIR}")
        return

    csv_files = sorted(
        path for path in DATA_DIR.glob("*.csv")
        if path.is_file()
    )

    if not csv_files:
        print("資料夾中沒有 CSV 檔案。")
        return

    manifest = load_manifest()
    manifest_duplicates = {
        name for name, entries in manifest.items()
        if len(entries) > 1
    }

    results = []

    for index, path in enumerate(csv_files, start=1):
        print(f"[{index}/{len(csv_files)}] 檢查 {path.name}")

        result = inspect_csv(path)

        entries = manifest.get(path.name, [])
        result["manifest_found"] = bool(entries)
        result["manifest_duplicate"] = (
            path.name in manifest_duplicates
        )

        if len(entries) == 1:
            entry = entries[0]

            try:
                manifest_size = int(entry.get("size_bytes") or -1)
            except (TypeError, ValueError):
                manifest_size = -1

            result["manifest_size_match"] = (
                manifest_size == result["size_bytes"]
            )

            expected_hash = (
                entry.get("sha256") or ""
            ).strip().lower()

            result["manifest_hash_match"] = (
                bool(expected_hash)
                and bool(result["sha256"])
                and expected_hash == result["sha256"].lower()
            )
        else:
            result["manifest_size_match"] = False
            result["manifest_hash_match"] = False

        results.append(result)

        status = (
            "正常"
            if result["readable"]
            and result["data_rows"] > 0
            and result["manifest_found"]
            and not result["manifest_duplicate"]
            and result["manifest_size_match"]
            and result["manifest_hash_match"]
            else "需檢查"
        )

        print(
            f"  {status} | "
            f"{result['size_bytes']:,} bytes | "
            f"{result['data_rows']:,} rows | "
            f"{result['column_count']} columns"
        )

        if result["error"]:
            print(f"  原因：{result['error']}")

    # =================================================
    # 重複內容檢查：依 SHA-256 比對
    # =================================================
    hash_counts = Counter(
        result["sha256"]
        for result in results
        if result["sha256"]
    )

    duplicate_hashes = {
        file_hash
        for file_hash, count in hash_counts.items()
        if count > 1
    }

    for result in results:
        result["duplicate_content"] = (
            bool(result["sha256"])
            and result["sha256"] in duplicate_hashes
        )

    # =================================================
    # 輸出詳細報告
    # =================================================
    report_fields = [
        "filename",
        "size_bytes",
        "data_rows",
        "column_count",
        "readable",
        "empty_file",
        "header_valid",
        "sha256",
        "manifest_found",
        "manifest_duplicate",
        "manifest_size_match",
        "manifest_hash_match",
        "duplicate_content",
        "error",
    ]

    with REPORT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=report_fields,
        )
        writer.writeheader()
        writer.writerows(results)

    # =================================================
    # 統計結果
    # =================================================
    readable_count = sum(
        result["readable"] for result in results
    )

    nonempty_count = sum(
        result["readable"] and result["data_rows"] > 0
        for result in results
    )

    manifest_found_count = sum(
        result["manifest_found"] for result in results
    )

    hash_match_count = sum(
        result["manifest_hash_match"] for result in results
    )

    size_match_count = sum(
        result["manifest_size_match"] for result in results
    )

    duplicate_content_count = sum(
        result["duplicate_content"] for result in results
    )

    total_bytes = sum(
        result["size_bytes"] for result in results
    )

    total_rows = sum(
        result["data_rows"] for result in results
    )

    passed_count = sum(
        result["readable"]
        and result["data_rows"] > 0
        and result["manifest_found"]
        and not result["manifest_duplicate"]
        and result["manifest_size_match"]
        and result["manifest_hash_match"]
        and not result["duplicate_content"]
        for result in results
    )

    summary_lines = [
        "========== CSV 品質檢查結果 ==========",
        f"預期檔案數：{EXPECTED_FILES}",
        f"實際 CSV 檔案數：{len(csv_files)}",
        f"可正常解析：{readable_count}",
        f"有資料列：{nonempty_count}",
        f"Manifest 有對應紀錄：{manifest_found_count}",
        f"Manifest 大小相符：{size_match_count}",
        f"Manifest SHA-256 相符：{hash_match_count}",
        f"重複內容檔案數：{duplicate_content_count}",
        f"全部檢查通過：{passed_count}",
        f"總檔案大小：{total_bytes:,} bytes",
        f"總檔案大小：{total_bytes / (1024 ** 2):.2f} MiB",
        f"總資料列數：{total_rows:,}",
        f"詳細報告：{REPORT_FILE.resolve()}",
    ]

    if len(csv_files) != EXPECTED_FILES:
        summary_lines.append(
            f"注意：檔案數與預期的 {EXPECTED_FILES} 個不同。"
        )

    summary_lines.append(
        "注意：檢查通過不代表資料授權已確認，"
        "也不代表所有指標在統計意義上互不相關。"
    )

    SUMMARY_FILE.write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8-sig",
    )

    print("\n" + "\n".join(summary_lines))


if __name__ == "__main__":
    main()