from pathlib import Path
from minio import Minio
from minio.error import S3Error
import os

# 專案路徑
PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_ROOT / "dataset"

# MinIO 設定
client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False
)

BUCKET_NAME = "compression-test"

# 五種資料集
DATA_TYPES = ["csv", "jpg", "json", "txt", "zip"]


def main():
    # 建立 Bucket
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"建立 Bucket：{BUCKET_NAME}")

    total = 0

    for data_type in DATA_TYPES:
        folder = DATASET_DIR / data_type

        if not folder.exists():
            print(f"[略過] 找不到資料夾：{folder}")
            continue

        files = [p for p in folder.rglob("*") if p.is_file()]

        print(f"\n開始上傳 {data_type}，共 {len(files)} 個檔案")

        for file_path in files:
            object_name = file_path.relative_to(DATASET_DIR).as_posix()

            client.fput_object(
                BUCKET_NAME,
                object_name,
                str(file_path)
            )

            total += 1
            print(f"[成功] {object_name}")

    print("\n========== 上傳完成 ==========")
    print(f"總上傳檔案數：{total}")

    for data_type in DATA_TYPES:
        objects = list(
            client.list_objects(
                BUCKET_NAME,
                prefix=f"{data_type}/",
                recursive=True
            )
        )
        print(f"{data_type}: {len(objects)} 個檔案")


if __name__ == "__main__":
    main()