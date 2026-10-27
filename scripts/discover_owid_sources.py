from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import time

import requests
from owid.catalog import Client

# =====================================================
# 設定
# =====================================================
TARGET_SOURCES = 100

# 每次搜尋先收集多少個候選圖表
CANDIDATE_BUFFER = 150

MIN_DATA_ROWS = 1
REQUEST_DELAY = 1.0
TIMEOUT = 45

CANDIDATES_CSV = Path("owid_source_candidates.csv")
VALIDATED_CSV = Path("owid_sources.csv")
REPORT_CSV = Path("owid_discovery_report.csv")

HEADERS = {
    "User-Agent": "StudentDatasetResearch/1.0 (educational project)"
}

SEARCH_TOPICS = [
    "population",
    "demographics",
    "health",
    "life expectancy",
    "mortality",
    "education",
    "economy",
    "GDP",
    "poverty",
    "inequality",
    "employment",
    "energy",
    "electricity",
    "renewable energy",
    "climate change",
    "CO2 emissions",
    "air pollution",
    "biodiversity",
    "agriculture",
    "food",
    "water",
    "migration",
    "urbanization",
    "internet",
    "technology",
    "trade",
    "government",
    "democracy",
    "conflict",
    "COVID-19",
]

session = requests.Session()
session.headers.update(HEADERS)


def get(url):
    """GET request with timeout and conservative delay."""
    response = session.get(url, timeout=TIMEOUT)
    time.sleep(REQUEST_DELAY)
    return response


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def discover_charts():
    """
    依照主題搜尋圖表。
    累積到 CANDIDATE_BUFFER 個不同 slug 就先停止。
    若候選不足，則繼續搜尋下一個主題。
    """
    client = Client(timeout=TIMEOUT)
    found = {}

    for topic in SEARCH_TOPICS:
        if len(found) >= CANDIDATE_BUFFER:
            break

        print(f"\n搜尋主題：{topic}")

        try:
            results = client.charts.search(
                topic,
                limit=100,
                page=0,
            )

            for item in results:
                slug = getattr(item, "slug", None)
                title = getattr(item, "title", None)
                url = getattr(item, "url", None)

                if not slug:
                    continue

                slug = str(slug).strip().strip("/")

                # 只接受單一 Grapher slug
                if not slug or "/" in slug:
                    continue

                if slug not in found:
                    found[slug] = {
                        "slug": slug,
                        "title_from_search": title or "",
                        "chart_url": (
                            f"https://ourworldindata.org/grapher/{slug}"
                        ),
                        "search_result_url": url or "",
                    }

                    if len(found) >= CANDIDATE_BUFFER:
                        break

            print(f"目前累積不同圖表：{len(found)}")

        except Exception as exc:
            print(f"此主題搜尋失敗：{exc}")

    return list(found.values())


def validate_chart(source):
    """驗證 CSV 與 metadata，取得資料列數及圖表標題。"""
    slug = source["slug"]

    result = {
        **source,
        "status": "rejected",
        "csv_http": "",
        "metadata_http": "",
        "title": "",
        "data_rows": 0,
        "column_count": 0,
        "citation": "",
        "license_status": "needs_manual_review",
        "reason": "",
    }

    csv_url = f"https://ourworldindata.org/grapher/{slug}.csv"
    metadata_url = (
        f"https://ourworldindata.org/grapher/{slug}.metadata.json"
    )

    result["csv_url"] = csv_url
    result["metadata_url"] = metadata_url

    try:
        csv_response = get(csv_url)
        result["csv_http"] = csv_response.status_code

        if csv_response.status_code != 200:
            result["reason"] = (
                f"CSV HTTP {csv_response.status_code}"
            )
            return result

        text = csv_response.content.decode("utf-8-sig")
        reader = csv.reader(text.splitlines())

        try:
            header = next(reader)
        except StopIteration:
            result["reason"] = "CSV is empty"
            return result

        if not header:
            result["reason"] = "CSV has no header"
            return result

        data_rows = sum(
            1
            for row in reader
            if row and any(value.strip() for value in row)
        )

        result["data_rows"] = data_rows
        result["column_count"] = len(header)

        if data_rows < MIN_DATA_ROWS:
            result["reason"] = "No valid data rows"
            return result

        metadata_response = get(metadata_url)
        result["metadata_http"] = metadata_response.status_code

        if metadata_response.status_code != 200:
            result["reason"] = (
                f"Metadata HTTP {metadata_response.status_code}"
            )
            return result

        metadata = metadata_response.json()
        chart = metadata.get("chart", {})
        title = chart.get("title", "")

        if not title:
            result["reason"] = "Metadata has no chart title"
            return result

        result["title"] = title
        result["citation"] = chart.get("citation", "")
        result["license_status"] = "needs_manual_review"
        result["reason"] = (
            "CSV and metadata verified; license needs manual review"
        )
        result["status"] = "valid"

    except Exception as exc:
        result["reason"] = f"{type(exc).__name__}: {exc}"

    return result


def main():
    # -------------------------------------------------
    # 第一階段：搜尋候選來源
    # -------------------------------------------------
    candidates = discover_charts()

    candidate_fields = [
        "slug",
        "title_from_search",
        "chart_url",
        "search_result_url",
    ]

    write_csv(
        CANDIDATES_CSV,
        candidates,
        candidate_fields,
    )

    print("\n========== 候選搜尋完成 ==========")
    print(f"不同候選圖表：{len(candidates)}")
    print("開始逐一驗證……")

    # -------------------------------------------------
    # 第二階段：驗證來源
    # 有效來源達 100 個就停止
    # -------------------------------------------------
    results = []
    valid_by_slug = {}

    for index, source in enumerate(candidates, start=1):
        if len(valid_by_slug) >= TARGET_SOURCES:
            print(f"\n已取得 {TARGET_SOURCES} 個有效指標，停止驗證。")
            break

        print(
            f"[{index}/{len(candidates)}] "
            f"{source['slug']}"
        )

        result = validate_chart(source)
        results.append(result)

        if result["status"] == "valid":
            valid_by_slug[result["slug"]] = result

        print(
            f"  {result['status']} | "
            f"{result['data_rows']:,} rows | "
            f"目前有效：{len(valid_by_slug)}"
        )

    # -------------------------------------------------
    # 第三階段：輸出驗證報告
    # -------------------------------------------------
    report_fields = [
        "slug",
        "title",
        "chart_url",
        "csv_url",
        "metadata_url",
        "search_result_url",
        "status",
        "csv_http",
        "metadata_http",
        "data_rows",
        "column_count",
        "citation",
        "license_status",
        "reason",
    ]

    write_csv(
        REPORT_CSV,
        results,
        report_fields,
    )

    valid = list(valid_by_slug.values())[:TARGET_SOURCES]

    print("\n========== 探索結果 ==========")
    print(f"候選圖表：{len(candidates)}")
    print(f"已驗證圖表：{len(results)}")
    print(f"有效不同指標：{len(valid)}")
    print(f"候選清單：{CANDIDATES_CSV.resolve()}")
    print(f"驗證報告：{REPORT_CSV.resolve()}")

    # -------------------------------------------------
    # 第四階段：產生 100 個來源清單
    # -------------------------------------------------
    if len(valid) < TARGET_SOURCES:
        print(
            f"\n目前只有 {len(valid)} 個有效指標，"
            f"未達目標 {TARGET_SOURCES} 個。"
        )
        print(
            "請增加 CANDIDATE_BUFFER，或增加搜尋主題及分頁，"
            "再重新執行。"
        )
        print("不會複製資料或重複計算相同 slug。")
        return

    timestamp = datetime.now(timezone.utc).isoformat()

    source_rows = []

    for item in valid:
        source_rows.append({
            "slug": item["slug"],
            "title": item["title"],
            "chart_url": item["chart_url"],
            "csv_url": item["csv_url"],
            "metadata_url": item["metadata_url"],
            "data_rows": item["data_rows"],
            "column_count": item["column_count"],
            "citation": item["citation"],
            "license_status": item["license_status"],
            "checked_at_utc": timestamp,
        })

    write_csv(
        VALIDATED_CSV,
        source_rows,
        [
            "slug",
            "title",
            "chart_url",
            "csv_url",
            "metadata_url",
            "data_rows",
            "column_count",
            "citation",
            "license_status",
            "checked_at_utc",
        ],
    )

    print(f"\n已建立 {len(source_rows)} 個不同指標的來源清單：")
    print(VALIDATED_CSV.resolve())
    print(
        "注意：來源驗證成功不代表授權已確認。"
        "正式下載前，請檢查各圖表與底層資料來源的授權。"
    )


if __name__ == "__main__":
    main()
