from pathlib import Path
from minio import Minio
import gzip
import os
import tempfile

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

BUCKET_NAME = "compression-benchmark"

DATA_TYPES = ["csv", "jpg", "json", "txt", "zip"]


def upload_original(file_path, data_type):
    """上傳原始檔案至 original/"""

    relative_path = file_path.relative_to(DATASET_DIR).as_posix()
    object_name = f"original/{relative_path}"

    client.fput_object(
        BUCKET_NAME,
        object_name,
        str(file_path)
    )

    print(f"[Original] {object_name}")


def upload_gzip(file_path, data_type):
    """壓縮檔案後上傳至 gzip/"""

    relative_path = file_path.relative_to(DATASET_DIR)
    gzip_object_name = f"gzip/{relative_path.as_posix()}.gz"

    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        with open(file_path, "rb") as source:
            with gzip.open(temp_path, "wb", compresslevel=6) as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)

        client.fput_object(
            BUCKET_NAME,
            gzip_object_name,
            str(temp_path),
            content_type="application/gzip"
        )

        print(f"[Gzip] {gzip_object_name}")

    finally:
        temp_path.unlink(missing_ok=True)


def main():

    # 建立 Bucket
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"[建立] Bucket：{BUCKET_NAME}")

    original_total = 0
    gzip_total = 0

    for data_type in DATA_TYPES:

        folder = DATASET_DIR / data_type

        if not folder.exists():
            print(f"[略過] 找不到資料夾：{folder}")
            continue

        files = sorted(p for p in folder.rglob("*") if p.is_file())

        print(f"\n========== {data_type} ==========")
        print(f"檔案數量：{len(files)}")

        for file_path in files:

            # 上傳原始檔案
            upload_original(file_path, data_type)
            original_total += 1

            # Gzip 壓縮並上傳
            upload_gzip(file_path, data_type)
            gzip_total += 1

    print("\n========== 上傳完成 ==========")
    print(f"Bucket：{BUCKET_NAME}")
    print(f"Original：{original_total} 個檔案")
    print(f"Gzip：{gzip_total} 個檔案")

    print("\n========== MinIO 檔案統計 ==========")

    for prefix in ["original/", "gzip/"]:

        objects = list(
            client.list_objects(
                BUCKET_NAME,
                prefix=prefix,
                recursive=True
            )
        )

        print(f"{prefix}: {len(objects)} 個檔案")


if __name__ == "__main__":
    main()