
from pathlib import Path
from urllib.parse import urljoin
import csv
import time

import requests
from bs4 import BeautifulSoup

URL = "https://www.gutenberg.org/browse/scores/top.html"
OUTPUT_DIR = Path("dataset")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "gutenberg_top100_yesterday.csv"

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}

def main():
    print("正在讀取 Project Gutenberg Top 100 頁面……")

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 找到標題「Top 100 EBooks yesterday」
    heading = soup.find(
        lambda tag: tag.name in ("h2", "h3")
        and "Top 100 EBooks yesterday" in tag.get_text(" ", strip=True)
    )

    if heading is None:
        raise RuntimeError(
            "找不到 Top 100 EBooks yesterday 區塊，"
            "請檢查網頁結構是否已變更。"
        )

    # 只解析該標題後、下一個同層標題前的區域
    books = []
    seen_urls = set()

    for element in heading.find_all_next():
        if element.name in ("h2", "h3"):
            break

        if element.name != "a":
            continue

        href = element.get("href", "").strip()
        title = element.get_text(" ", strip=True)

        if not href or not title:
            continue

        full_url = urljoin(URL, href)

        # 僅接受 Gutenberg 電子書頁面
        if not (
            full_url.startswith("https://www.gutenberg.org/ebooks/")
        ):
            continue

        # 排除可能的子頁路徑，只保留 /ebooks/數字
        import re
        if not re.fullmatch(
            r"https://www\.gutenberg\.org/ebooks/\d+",
            full_url,
        ):
            continue

        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)

        books.append({
            "rank": len(books) + 1,
            "title": title,
            "book_url": full_url,
        })

        if len(books) == 100:
            break

    if not books:
        raise RuntimeError(
            "沒有擷取到書籍連結，可能是 HTML 結構已改變。"
        )

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["rank", "title", "book_url"],
        )
        writer.writeheader()
        writer.writerows(books)

    print(f"完成：擷取到 {len(books)} 個書籍連結")
    print(f"CSV：{OUTPUT_CSV.resolve()}")
    print("\n前 10 筆：")

    for book in books[:10]:
        print(
            f"{book['rank']:>3}. "
            f"{book['title']} — {book['book_url']}"
        )

if __name__ == "__main__":
    main()
