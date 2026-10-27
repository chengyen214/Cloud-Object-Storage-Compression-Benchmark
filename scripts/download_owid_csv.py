from pathlib import Path
import csv
import hashlib
import time

import requests

# =====================================================
# 設定
# =====================================================
SOURCE_FILE = Path("owid_sources.csv")
OUTPUT_DIR = Path("dataset/csv")
MANIFEST_FILE = Path("dataset/dataset_manifest.csv")
REPORT_FILE = Path("dataset/owid_download_report.csv")

REQUEST_DELAY = 1.0
TIMEOUT = 60

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}

session = requests.Session()
session.headers.update(HEADERS)


def sha256_file(path):
    """計算檔案 SHA-256。"""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def safe_filename(index, slug):
    """建立安全且不重複的檔名。"""
    safe_slug = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in slug
    )
    return f"{index:03d}_{safe_slug}.csv"


def main():
    if not SOURCE_FILE.exists():
        print(f"找不到來源清單：{SOURCE_FILE.resolve()}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)

    with SOURCE_FILE.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        sources = list(csv.DictReader(file))

    # 確認來源清單存在必要欄位
    required = {"slug", "title", "csv_url"}
    if not sources or not required.issubset(sources[0].keys()):
        print("來源清單缺少必要欄位：slug、title、csv_url")
        return

    # 只保留不同 slug，避免重複下載同一指標
    unique_sources = []
    seen = set()

    for source in sources:
        slug = source["slug"].strip()

        if slug and slug not in seen:
            seen.add(slug)
            unique_sources.append(source)

    print(f"來源清單筆數：{len(sources)}")
    print(f"不同指標數量：{len(unique_sources)}")

    report = []
    manifest = []

    for index, source in enumerate(unique_sources, start=1):
        slug = source["slug"].strip()
        title = source.get("title", "").strip()
        url = source["csv_url"].strip()
        filename = safe_filename(index, slug)
        output_path = OUTPUT_DIR / filename

        print(f"\n[{index}/{len(unique_sources)}] {title}")
        print(f"來源：{url}")

        record = {
            "slug": slug,
            "title": title,
            "csv_url": url,
            "filename": filename,
            "status": "failed",
            "http_status": "",
            "size_bytes": 0,
            "sha256": "",
            "reason": "",
        }

        try:
            response = session.get(
                url,
                timeout=TIMEOUT,
            )
            time.sleep(REQUEST_DELAY)

            record["http_status"] = response.status_code

            if response.status_code != 200:
                record["reason"] = (
                    f"HTTP {response.status_code}"
                )
                report.append(record)
                print(f"下載失敗：{record['reason']}")
                continue

            content = response.content

            if not content.strip():
                record["reason"] = "Empty response"
                report.append(record)
                print("下載失敗：回應內容為空")
                continue

            # 確認內容可以解碼，避免把錯誤頁面當成 CSV
            text = content.decode("utf-8-sig")
            reader = csv.reader(text.splitlines())

            try:
                header = next(reader)
            except StopIteration:
                record["reason"] = "CSV has no header"
                report.append(record)
                continue

            if not header or not any(value.strip() for value in header):
                record["reason"] = "CSV has invalid header"
                report.append(record)
                continue

            data_rows = sum(
                1
                for row in reader
                if row and any(value.strip() for value in row)
            )

            if data_rows == 0:
                record["reason"] = "CSV has no data rows"
                report.append(record)
                print("下載失敗：沒有資料列")
                continue

            # 寫入獨立 CSV 檔案
            output_path.write_bytes(content)

            file_size = output_path.stat().st_size
            file_hash = sha256_file(output_path)

            record["status"] = "success"
            record["size_bytes"] = file_size
            record["sha256"] = file_hash
            record["reason"] = f"{data_rows} data rows"

            manifest.append({
                "filename": filename,
                "file_type": "CSV",
                "category": "owid_indicator",
                "title": title,
                "source": url,
                "license": "needs_manual_review",
                "size_bytes": file_size,
                "sha256": file_hash,
            })

            print(
                f"下載成功 | {data_rows:,} rows | "
                f"{file_size:,} bytes"
            )

        except Exception as exc:
            record["reason"] = (
                f"{type(exc).__name__}: {exc}"
            )
            print(f"發生錯誤：{record['reason']}")

        report.append(record)

    # 輸出下載報告
    report_fields = [
        "slug",
        "title",
        "csv_url",
        "filename",
        "status",
        "http_status",
        "size_bytes",
        "sha256",
        "reason",
    ]

    with REPORT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=report_fields,
        )
        writer.writeheader()
        writer.writerows(report)

    # 輸出成功下載檔案的 manifest
    manifest_fields = [
        "filename",
        "file_type",
        "category",
        "title",
        "source",
        "license",
        "size_bytes",
        "sha256",
    ]

    with MANIFEST_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=manifest_fields,
        )
        writer.writeheader()
        writer.writerows(manifest)

    success_count = sum(
        1 for item in report
        if item["status"] == "success"
    )
    failure_count = len(report) - success_count

    print("\n========== 下載結果 ==========")
    print(f"成功：{success_count}")
    print(f"失敗：{failure_count}")
    print(f"CSV 資料夾：{OUTPUT_DIR.resolve()}")
    print(f"Manifest：{MANIFEST_FILE.resolve()}")
    print(f"下載報告：{REPORT_FILE.resolve()}")

    if success_count < len(unique_sources):
        print(
            "\n部分來源下載失敗，請查看 "
            "owid_download_report.csv。"
        )


if __name__ == "__main__":
    main()