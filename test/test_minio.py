import sys
from pathlib import Path

# 將專案根目錄加入 Python 搜尋路徑
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.minio_client import client, BUCKET_NAME
from app.storage import get_available_methods


def main():
    print("Bucket 是否存在：", client.bucket_exists(BUCKET_NAME))

    print("\n目前可用的壓縮方式：")

    for method in get_available_methods():
        print("-", method)


if __name__ == "__main__":
    main()