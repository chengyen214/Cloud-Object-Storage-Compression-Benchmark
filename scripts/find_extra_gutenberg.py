
from pathlib import Path
from urllib.parse import urljoin
import csv
import re
import hashlib
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.gutenberg.org/browse/scores/top.html"
OUTPUT_DIR = Path("dataset")
TXT_DIR = OUTPUT_DIR / "txt"

EXISTING_RESULTS = OUTPUT_DIR / "gutenberg_download_results.csv"
TOP100_CSV = OUTPUT_DIR / "gutenberg_top100_yesterday.csv"
EXTRA_RESULTS = OUTPUT_DIR / "gutenberg_extra_download_results.csv"

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}

def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def get_book_id(text):
    match = re.search(r"/ebooks/(\d+)", text or "")
    return match.group(1) if match else None

def main():
    TXT_DIR.mkdir(parents=True, exist_ok=True)

    # 收集已下載書籍 ID，避免重複
    downloaded_ids = set()

    for row in read_csv(EXISTING_RESULTS):
        for key, value in row.items():
            if key and value:
                book_id = get_book_id(value)
                if book_id:
                    downloaded_ids.add(book_id)

    # 也檢查 TXT 檔名中是否含 Gutenberg ID
    for path in TXT_DIR.glob("pg*.txt"):
        match = re.match(r"pg(\d+)", path.stem, re.I)
        if match:
            downloaded_ids.add(match.group(1))

    # 將原始 Top 100 清單納入排除名單
    for row in read_csv(TOP100_CSV):
        book_id = get_book_id(row.get("book_url", ""))
        if book_id:
            downloaded_ids.add(book_id)

    print(f"目前已排除的書籍 ID：{len(downloaded_ids)} 筆")

    response = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    heading = soup.find(
        lambda tag: tag.name in ("h2", "h3")
        and "Top 100 EBooks last 7 days"
        in tag.get_text(" ", strip=True)
    )

    if heading is None:
        raise RuntimeError(
            "找不到 Top 100 EBooks last 7 days 區塊。"
            "請確認 Gutenberg 網頁標題是否已變更。"
        )

    candidates = []
    seen = set()

    for element in heading.find_all_next():
        if element.name in ("h2", "h3"):
            break
        if element.name != "a":
            continue

        href = element.get("href", "").strip()
        title = element.get_text(" ", strip=True)
        full_url = urljoin(BASE_URL, href)

        match = re.fullmatch(
            r"https://www\.gutenberg\.org/ebooks/(\d+)",
            full_url
        )
        if not match or not title:
            continue

        book_id = match.group(1)
        if book_id in downloaded_ids or book_id in seen:
            continue

        seen.add(book_id)
        candidates.append({
            "book_id": book_id,
            "title": title,
            "book_url": full_url,
        })

    print(f"last 7 days 清單中，未出現於排除名單的書：{len(candidates)} 本")

    # 先只列出候選書，不自動下載，讓你確認後再執行下載
    for i, book in enumerate(candidates[:10], start=1):
        print(f"{i}. {book['title']} (ID: {book['book_id']})")

    if not candidates:
        print("沒有找到候選書。請檢查下載結果 CSV 的欄位與檔名格式。")
        return

    print(
        "\n提醒：此程式目前只列出候選書，尚未下載。"
        "請先確認候選書與原始下載紀錄，再選擇要補的書。"
    )

if __name__ == "__main__":
    main()
