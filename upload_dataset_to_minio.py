from pathlib import Path
from minio import Minio
import zstandard as zstd
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

# Zstd Level 6
compressor = zstd.ZstdCompressor(level=6)
PREFIX = "zstd_level_6"


def upload_zstd(file_path):
    """壓縮檔案後上傳至 zstd_level_6/"""

    relative_path = file_path.relative_to(DATASET_DIR).as_posix()
    object_name = f"{PREFIX}/{relative_path}.zst"

    with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        with open(file_path, "rb") as source:
            with open(temp_path, "wb") as target:
                compressor.copy_stream(
                    source,
                    target,
                    size=file_path.stat().st_size
                )

        client.fput_object(
            BUCKET_NAME,
            object_name,
            str(temp_path),
            content_type="application/zstd"
        )

        print(f"[Zstd Level 6] {object_name}")

    finally:
        temp_path.unlink(missing_ok=True)


def main():
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"[建立] Bucket：{BUCKET_NAME}")

    total = 0

    for data_type in DATA_TYPES:
        folder = DATASET_DIR / data_type

        if not folder.exists():
            print(f"[略過] 找不到資料夾：{folder}")
            continue

        files = sorted(p for p in folder.rglob("*") if p.is_file())

        print(f"\n========== {data_type} ==========")
        print(f"檔案數量：{len(files)}")

        for file_path in files:
            upload_zstd(file_path)
            total += 1

    print("\n========== 上傳完成 ==========")
    print(f"Bucket：{BUCKET_NAME}")
    print(f"Zstd Level 6：{total} 個檔案")

    print("\n========== MinIO 檔案統計 ==========")

    count = sum(
        1 for _ in client.list_objects(
            BUCKET_NAME,
            prefix=f"{PREFIX}/",
            recursive=True
        )
    )

    print(f"{PREFIX}/: {count} 個檔案")


if __name__ == "__main__":
    main()