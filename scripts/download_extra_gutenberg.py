
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import re
import time

import requests

# =========================
# 路徑設定
# =========================
TXT_DIR = Path("dataset/txt")
RESULT_CSV = Path("dataset/gutenberg_extra_download_results.csv")

TXT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 指定需要補上的書籍
# 只補編號 072、088
# =========================
BOOKS = [
    {
        "number": 72,
        "id": "42324",
        "title": "Frankenstein",
    },
    {
        "number": 88,
        "id": "26184",
        "title": "Simple Sabotage Field Manual",
    },
]

BASE_URL = "https://gutenberg.pglaf.org/cache/epub/{id}/pg{id}.txt"

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}


def get_existing_book_ids():
    """從原始及補下載紀錄取得已記錄的 Gutenberg ID。"""
    ids = set()

    csv_paths = [
        Path("dataset/gutenberg_download_results.csv"),
        RESULT_CSV,
    ]

    for csv_path in csv_paths:
        if not csv_path.exists():
            continue

        with csv_path.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            for row in csv.DictReader(f):
                for key in (
                    "book_id",
                    "book_url",
                    "source_url",
                    "url",
                    "filename",
                    "file",
                ):
                    value = row.get(key, "")
                    if not value:
                        continue

                    match = re.search(
                        r"(?:/ebooks/|pg)(\d+)",
                        value,
                        re.IGNORECASE,
                    )
                    if match:
                        ids.add(match.group(1))

    # 檢查目前資料夾中已存在的 Gutenberg 檔案
    for path in TXT_DIR.glob("book_*.txt"):
        match = re.fullmatch(
            r"book_\d{3}_(\d+)",
            path.stem,
        )
        if match:
            ids.add(match.group(1))

    return ids


def download_book(session, book):
    """下載一本書，成功才寫入目標檔案。"""
    number = book["number"]
    book_id = book["id"]
    title = book["title"]

    filename = f"book_{number:03d}_{book_id}.txt"
    output_path = TXT_DIR / filename
    url = BASE_URL.format(id=book_id)

    # 不覆蓋既有檔案
    if output_path.exists():
        if output_path.stat().st_size > 0:
            content = output_path.read_bytes()

            return {
                "book_id": book_id,
                "title": title,
                "filename": filename,
                "status": "already_exists",
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "source_url": url,
                "downloaded_at_utc":
                    datetime.now(timezone.utc).isoformat(),
            }

        return {
            "book_id": book_id,
            "title": title,
            "filename": filename,
            "status": "failed_existing_empty_file",
            "size_bytes": 0,
            "sha256": "",
            "source_url": url,
            "downloaded_at_utc":
                datetime.now(timezone.utc).isoformat(),
        }

    response = session.get(url, timeout=60)
    response.raise_for_status()

    content = response.content

    # 基本內容驗證，避免將錯誤頁面存成 TXT
    if len(content) < 1000:
        raise ValueError("檔案太小，可能不是有效的電子書。")

    if b"project gutenberg" not in content[:500].lower():
        raise ValueError(
            "檔案開頭未找到 Project Gutenberg 標記，"
            "請確認下載內容。"
        )

    # 使用 xb 模式，避免意外覆蓋檔案
    with output_path.open("xb") as f:
        f.write(content)

    return {
        "book_id": book_id,
        "title": title,
        "filename": filename,
        "status": "downloaded",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "source_url": url,
        "downloaded_at_utc":
            datetime.now(timezone.utc).isoformat(),
    }


def main():
    print("=" * 55)
    print("Project Gutenberg TXT 缺號補下載")
    print("=" * 55)

    # 檢查目前編號是否已經補齊
    existing_numbers = set()

    for path in TXT_DIR.glob("book_*.txt"):
        match = re.fullmatch(
            r"book_(\d{3})_\d+",
            path.stem,
        )
        if match:
            existing_numbers.add(int(match.group(1)))

    print(f"目前 book_*.txt 數量：{len(existing_numbers)}")
    print(
        "目前缺少編號：",
        [
            n for n in range(1, 101)
            if n not in existing_numbers
        ],
    )

    existing_ids = get_existing_book_ids()
    session = requests.Session()
    session.headers.update(HEADERS)

    rows = []

    for book in BOOKS:
        number = book["number"]
        book_id = book["id"]
        filename = f"book_{number:03d}_{book_id}.txt"

        # 如果編號已被其他檔案占用，不自動覆蓋
        occupied = [
            p for p in TXT_DIR.glob(f"book_{number:03d}_*.txt")
            if p.name != filename
        ]

        if occupied:
            print(
                f"[略過] 編號 {number:03d} 已被其他檔案使用："
                f"{occupied[0].name}"
            )
            rows.append({
                "book_id": book_id,
                "title": book["title"],
                "filename": filename,
                "status": "failed_number_occupied",
                "size_bytes": 0,
                "sha256": "",
                "source_url": BASE_URL.format(id=book_id),
                "downloaded_at_utc":
                    datetime.now(timezone.utc).isoformat(),
            })
            continue

        # 如果同一本書已存在於其他編號，避免重複
        if book_id in existing_ids:
            target = TXT_DIR / filename

            if target.exists() and target.stat().st_size > 0:
                content = target.read_bytes()
                status = "already_exists"
                size_bytes = len(content)
                sha256 = hashlib.sha256(content).hexdigest()
            else:
                print(
                    f"[略過] Gutenberg ID {book_id} "
                    "已存在於下載紀錄，避免重複下載。"
                )
                status = "skipped_duplicate_id"
                size_bytes = 0
                sha256 = ""

            rows.append({
                "book_id": book_id,
                "title": book["title"],
                "filename": filename,
                "status": status,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "source_url": BASE_URL.format(id=book_id),
                "downloaded_at_utc":
                    datetime.now(timezone.utc).isoformat(),
            })
            continue

        try:
            result = download_book(session, book)
            rows.append(result)

            if result["status"] == "downloaded":
                existing_ids.add(book_id)
                print(
                    f"[成功] {result['filename']} | "
                    f"{result['size_bytes']:,} bytes"
                )
            else:
                print(
                    f"[已存在] {result['filename']} | "
                    f"{result['size_bytes']:,} bytes"
                )

        except Exception as exc:
            print(
                f"[失敗] {filename} | {exc}"
            )

            rows.append({
                "book_id": book_id,
                "title": book["title"],
                "filename": filename,
                "status": "failed",
                "size_bytes": 0,
                "sha256": "",
                "source_url": BASE_URL.format(id=book_id),
                "downloaded_at_utc":
                    datetime.now(timezone.utc).isoformat(),
            })

        time.sleep(2)

    # 追加寫入結果，不覆蓋先前補下載紀錄
    fields = [
        "book_id",
        "title",
        "filename",
        "status",
        "size_bytes",
        "sha256",
        "source_url",
        "downloaded_at_utc",
    ]

    file_has_content = (
        RESULT_CSV.exists() and RESULT_CSV.stat().st_size > 0
    )

    with RESULT_CSV.open(
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)

        if not file_has_content:
            writer.writeheader()

        writer.writerows(rows)

    # 最後重新統計編號
    final_numbers = set()

    for path in TXT_DIR.glob("book_*.txt"):
        match = re.fullmatch(
            r"book_(\d{3})_\d+",
            path.stem,
        )
        if match:
            final_numbers.add(int(match.group(1)))

    missing = [
        n for n in range(1, 101)
        if n not in final_numbers
    ]

    print("\n" + "=" * 55)
    print("補下載流程結束")
    print(f"目前 book_*.txt 數量：{len(final_numbers)}")
    print(f"剩餘缺少編號：{missing}")
    print(f"結果清單：{RESULT_CSV.resolve()}")
    print("=" * 55)


if __name__ == "__main__":
    main()
