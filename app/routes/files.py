import gzip
import io

import lz4.frame
import zstandard as zstd

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.minio_client import client, BUCKET_NAME

router = APIRouter()


# ==================================================
# GET /files/{object_id}
# 讀取 MinIO 物件、解壓縮並回傳原始檔案
# ==================================================
@router.get("/files/{object_id:path}")
def get_file(object_id: str):

    parts = object_id.split("/")

    if len(parts) < 3:
        raise HTTPException(
            status_code=400,
            detail="無效的物件路徑"
        )

    method = parts[0]

    if method not in ("original", "gzip", "lz4", "zstd"):
        raise HTTPException(
            status_code=400,
            detail="不支援的壓縮方式"
        )

    try:
        # 從 MinIO 讀取物件
        response = client.get_object(
            BUCKET_NAME,
            object_id
        )

        try:
            stored_data = response.read()
        finally:
            response.close()
            response.release_conn()

        # 依照壓縮方式解壓縮
        if method == "original":

            original_data = stored_data

        elif method == "gzip":

            original_data = gzip.decompress(stored_data)

        elif method == "lz4":

            original_data = lz4.frame.decompress(stored_data)

        elif method == "zstd":

            decompressor = zstd.ZstdDecompressor()
            original_data = decompressor.decompress(stored_data)

        # 取得原始檔案名稱
        file_name = parts[-1]

        suffix_map = {
            "gzip": ".gz",
            "lz4": ".lz4",
            "zstd": ".zst"
        }

        suffix = suffix_map.get(method)

        if suffix and file_name.lower().endswith(suffix):
            file_name = file_name[:-len(suffix)]

        # 回傳原始檔案
        return StreamingResponse(
            io.BytesIO(original_data),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{file_name}"'
                )
            }
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"檔案讀取或解壓縮失敗：{str(e)}"
        )


# ==================================================
# GET /health
# 檢查 FastAPI 與 MinIO 狀態
# ==================================================
@router.get("/health")
def health_check():

    try:
        # 檢查 MinIO Bucket 是否存在
        bucket_exists = client.bucket_exists(BUCKET_NAME)

        if not bucket_exists:
            return {
                "status": "unhealthy",
                "fastapi": "running",
                "minio": "disconnected",
                "message": "MinIO Bucket 不存在"
            }

        return {
            "status": "healthy",
            "fastapi": "running",
            "minio": "connected",
            "bucket": BUCKET_NAME
        }

    except Exception as e:

        return {
            "status": "unhealthy",
            "fastapi": "running",
            "minio": "disconnected",
            "message": str(e)
        }