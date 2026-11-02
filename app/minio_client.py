import os
from minio import Minio

# MinIO 設定
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]

BUCKET_NAME = "compression-benchmark"

# 建立 MinIO Client
client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)