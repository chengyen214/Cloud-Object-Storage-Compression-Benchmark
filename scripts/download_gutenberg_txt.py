
from pathlib import Path
from urllib.parse import urlparse
import csv
import hashlib
import re
import time

import requests

# 輸入排行榜 CSV
INPUT_CSV = Path("dataset/gutenberg_top100_yesterday.csv")

# TXT 輸出位置
OUTPUT_DIR = Path("dataset/txt")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 下載結果紀錄
RESULT_CSV = Path("dataset/gutenberg_download_results.csv")

# 已測試成功的 Gutenberg 鏡像站
MIRROR = "https://gutenberg.pglaf.org"

# 請求間隔
DELAY_SECONDS = 2

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"找不到排行榜清單：{INPUT_CSV}"
        )

    with INPUT_CSV.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        books = list(csv.DictReader(f))

    if not books:
        raise ValueError("排行榜 CSV 沒有資料。")

    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    total = min(100, len(books))

    for index, book in enumerate(books[:total], start=1):
        title = book.get("title", "").strip()
        book_url = book.get("book_url", "").strip()

        match = re.fullmatch(
            r"https://www\.gutenberg\.org/ebooks/(\d+)/?",
            book_url,
        )

        if not match:
            print(f"[{index}/{total}] 無效網址：{book_url}")
            results.append({
                "rank": index,
                "book_id": "",
                "title": title,
                "status": "invalid_book_url",
                "filename": "",
                "size_bytes": "",
                "sha256": "",
                "source_url": book_url,
            })
            continue

        book_id = match.group(1)
        filename = f"book_{index:03d}_{book_id}.txt"
        output_path = OUTPUT_DIR / filename

        # 跳過已經下載的檔案
        if output_path.exists() and output_path.stat().st_size > 0:
            content = output_path.read_bytes()
            print(f"[{index}/{total}] 已存在：{filename}")
            results.append({
                "rank": index,
                "book_id": book_id,
                "title": title,
                "status": "already_exists",
                "filename": filename,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "source_url": book_url,
            })
            continue

        download_url = (
            f"{MIRROR}/cache/epub/{book_id}/pg{book_id}.txt"
        )

        try:
            response = session.get(download_url, timeout=60)

            if response.status_code != 200:
                status = f"http_{response.status_code}"
                content = None
            elif not response.content:
                status = "empty_response"
                content = None
            elif "text/plain" not in response.headers.get(
                "Content-Type", ""
            ).lower():
                status = "unexpected_content_type"
                content = None
            elif b"The Project Gutenberg" not in response.content[:5000]:
                status = "unrecognized_content"
                content = None
            else:
                status = "success"
                content = response.content

            if content is not None:
                output_path.write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()

                results.append({
                    "rank": index,
                    "book_id": book_id,
                    "title": title,
                    "status": status,
                    "filename": filename,
                    "size_bytes": len(content),
                    "sha256": digest,
                    "source_url": download_url,
                })

                print(
                    f"[{index}/{total}] 成功：{title} "
                    f"({len(content):,} bytes)"
                )
            else:
                results.append({
                    "rank": index,
                    "book_id": book_id,
                    "title": title,
                    "status": status,
                    "filename": "",
                    "size_bytes": "",
                    "sha256": "",
                    "source_url": download_url,
                })

                print(f"[{index}/{total}] 失敗：{title} ({status})")

        except requests.RequestException as exc:
            status = f"request_error_{type(exc).__name__}"

            results.append({
                "rank": index,
                "book_id": book_id,
                "title": title,
                "status": status,
                "filename": "",
                "size_bytes": "",
                "sha256": "",
                "source_url": download_url,
            })

            print(f"[{index}/{total}] 請求失敗：{title} ({exc})")

        # 請求之間等待，避免連續大量存取
        if index < total:
            time.sleep(DELAY_SECONDS)

    fields = [
        "rank", "book_id", "title", "status",
        "filename", "size_bytes", "sha256", "source_url",
    ]

    with RESULT_CSV.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    successful = sum(
        row["status"] in ("success", "already_exists")
        for row in results
    )

    print("\n下載作業完成")
    print(f"處理筆數：{len(results)}")
    print(f"成功或已存在：{successful}")
    print(f"TXT 資料夾：{OUTPUT_DIR.resolve()}")
    print(f"結果清單：{RESULT_CSV.resolve()}")


if __name__ == "__main__":
    main()
