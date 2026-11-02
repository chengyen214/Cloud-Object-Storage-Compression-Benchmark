import requests

API_URL = "http://127.0.0.1:8000"

OBJECT_ID = (
    "original/csv/"
    "018_mobile-cellular-subscriptions-per-100-people.csv"
)

OUTPUT_FILE = "test_download_original.csv"


def test_get_original_file():

    url = f"{API_URL}/files/{OBJECT_ID}"

    print("=" * 60)
    print("GET /files/{object_id} Original 測試")
    print("=" * 60)

    print(f"物件路徑：{OBJECT_ID}")
    print(f"API URL：{url}")

    try:
        response = requests.get(url, timeout=120)

        print(f"\nHTTP Status Code：{response.status_code}")

        if response.status_code != 200:
            print("[失敗] API 請求失敗")
            print(response.text)
            return

        # 儲存 API 回傳檔案
        with open(OUTPUT_FILE, "wb") as f:
            f.write(response.content)

        print("[成功] API 成功回傳檔案")
        print(f"下載檔案：{OUTPUT_FILE}")
        print(f"檔案大小：{len(response.content):,} bytes")

        # 驗證 CSV 內容
        with open(OUTPUT_FILE, "rb") as f:
            content = f.read()

        try:
            text = content.decode("utf-8-sig")
            lines = text.splitlines()

            print(f"CSV 總行數：{len(lines):,}")
            print(f"CSV 欄位：{lines[0] if lines else '無資料'}")

            print("\n前 3 行內容：")

            for line in lines[:3]:
                print(line)

        except UnicodeDecodeError:
            print("[警告] 檔案無法使用 UTF-8 解碼")

        print("\n[測試完成] Original API 執行成功")

    except requests.exceptions.RequestException as e:
        print(f"[錯誤] 無法連線至 FastAPI：{e}")


if __name__ == "__main__":
    test_get_original_file()