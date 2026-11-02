import csv
import gzip
import io
import json
import time

import lz4.frame
import zstandard as zstd

from pathlib import Path
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates

from app.storage import get_available_methods, get_method_files
from app.minio_client import client, BUCKET_NAME

router = APIRouter()

APP_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


# ==================================================
# 第一層：顯示資料類型分類
# URL: /methods/gzip
# ==================================================
@router.get("/methods/{method}")
def method_page(request: Request, method: str):

    methods = get_available_methods()

    if method not in methods:
        raise HTTPException(status_code=404, detail="找不到此壓縮方式")

    files = get_method_files(method)

    grouped_files = {}

    for file in files:
        parts = file["path"].split("/")

        if len(parts) >= 3:
            data_type = parts[1]
        else:
            data_type = "other"

        grouped_files.setdefault(data_type, []).append(file)

    categories = [
        {
            "name": data_type,
            "count": len(category_files)
        }
        for data_type, category_files in sorted(grouped_files.items())
    ]

    return templates.TemplateResponse(
        request=request,
        name="method.html",
        context={
            "method": method,
            "categories": categories,
            "file_count": len(files)
        }
    )


# ==================================================
# 第二層：顯示指定資料類型的檔案
# URL: /methods/gzip/csv
# ==================================================
@router.get("/methods/{method}/{data_type}")
def category_page(
    request: Request,
    method: str,
    data_type: str
):

    methods = get_available_methods()

    if method not in methods:
        raise HTTPException(status_code=404, detail="找不到此壓縮方式")

    files = get_method_files(method)

    category_files = [
        file for file in files
        if len(file["path"].split("/")) >= 3
        and file["path"].split("/")[1] == data_type
    ]

    if not category_files:
        raise HTTPException(status_code=404, detail="找不到此資料類型")

    return templates.TemplateResponse(
        request=request,
        name="category.html",
        context={
            "method": method,
            "data_type": data_type,
            "files": category_files
        }
    )


# ==================================================
# 第三層：讀取、解壓縮並預覽選取檔案
# URL: POST /methods/{method}/preview
# ==================================================
@router.post("/methods/{method}/preview")
def preview_selected(
    request: Request,
    method: str,
    files: list[str] = Form(...)
):

    methods = get_available_methods()

    if method not in methods:
        raise HTTPException(status_code=404, detail="找不到此壓縮方式")

    # 確認選取的檔案都屬於目前壓縮方式
    valid_files = {
        item["path"] for item in get_method_files(method)
    }

    selected_files = list(dict.fromkeys(files))

    if not selected_files or any(
        path not in valid_files
        or not path.startswith(f"{method}/")
        for path in selected_files
    ):
        raise HTTPException(status_code=400, detail="選取的檔案無效")

    previews = []

    for object_name in selected_files:

        # ------------------------------------------
        # 1. 從 MinIO 讀取檔案
        # ------------------------------------------
        start_read = time.perf_counter()

        response = client.get_object(
            BUCKET_NAME,
            object_name
        )

        try:
            stored_data = response.read()

        finally:
            response.close()
            response.release_conn()

        read_time = time.perf_counter() - start_read

        # ------------------------------------------
        # 2. 依照壓縮方式解壓縮
        # ------------------------------------------
        start_decompress = time.perf_counter()

        try:

            if method == "original":

                # 原始檔案，不需要解壓縮
                original_data = stored_data

            elif method == "gzip":

                # Gzip 解壓縮
                original_data = gzip.decompress(stored_data)

            elif method == "lz4":

                # LZ4 Frame 解壓縮
                original_data = lz4.frame.decompress(stored_data)

            elif method == "zstd":

                # Zstandard 解壓縮
                decompressor = zstd.ZstdDecompressor()
                original_data = decompressor.decompress(stored_data)

            else:

                raise ValueError(
                    f"目前尚未支援 {method} 的解壓縮"
                )

        except Exception as e:

            raise HTTPException(
                status_code=500,
                detail=f"檔案處理失敗：{object_name}，原因：{e}"
            )

        decompress_time = time.perf_counter() - start_decompress

        # ------------------------------------------
        # 3. 判斷原始檔案類型
        # ------------------------------------------
        file_name = object_name.split("/")[-1]

        # 移除壓縮檔案副檔名
        suffix_map = {
            "gzip": ".gz",
            "lz4": ".lz4",
            "zstd": ".zst"
        }

        suffix = suffix_map.get(method)

        if suffix and file_name.lower().endswith(suffix):
            file_name = file_name[:-len(suffix)]

        extension = file_name.rsplit(".", 1)[-1].lower()

        original_size = len(original_data)
        stored_size = len(stored_data)

        # ------------------------------------------
        # 4. 建立個別檔案資訊
        # ------------------------------------------
        preview = {
            "name": file_name,
            "type": extension.upper(),

            # 檔案大小
            "original_size": original_size,
            "stored_size": stored_size,
            "saved_size": original_size - stored_size,

            # 壓縮率
            "compression_ratio": (
                stored_size / original_size * 100
                if original_size > 0 else 0
            ),

            "saving_rate": (
                (original_size - stored_size) / original_size * 100
                if original_size > 0 else 0
            ),

            # 效能資訊
            "read_time": round(read_time * 1000, 3),
            "decompress_time": round(decompress_time * 1000, 3),

            # 檔案內容
            "content": None,
            "headers": [],
            "rows": []
        }

        # ------------------------------------------
        # 5. 依照檔案類型解析內容
        # ------------------------------------------
        try:

            if extension == "csv":

                text = original_data.decode("utf-8-sig")
                rows = list(csv.reader(io.StringIO(text)))

                preview["headers"] = rows[0] if rows else []
                preview["rows"] = rows[1:101] if rows else []

            elif extension == "json":

                parsed = json.loads(
                    original_data.decode("utf-8-sig")
                )

                preview["content"] = json.dumps(
                    parsed,
                    ensure_ascii=False,
                    indent=2
                )

            elif extension in ("txt", "log"):

                preview["content"] = original_data.decode(
                    "utf-8",
                    errors="replace"
                )[:20000]

            elif extension in ("jpg", "jpeg"):

                preview["content"] = "圖片預覽功能尚未加入。"

            elif extension == "zip":

                preview["content"] = "ZIP 檔案已讀取，目前尚未展開內部內容。"

            else:

                preview["content"] = "目前尚未支援此檔案類型的預覽。"

        except Exception as e:

            preview["content"] = f"檔案解析失敗：{e}"

        previews.append(preview)

    # ==================================================
    # 6. 計算整體效能統計
    # ==================================================

    file_count = len(previews)

    # ------------------------------------------
    # 儲存效率
    # ------------------------------------------
    total_original_size = sum(
        item["original_size"] for item in previews
    )

    total_stored_size = sum(
        item["stored_size"] for item in previews
    )

    total_saved_size = total_original_size - total_stored_size

    compression_ratio = (
        total_stored_size / total_original_size * 100
        if total_original_size > 0 else 0
    )

    saving_rate = (
        total_saved_size / total_original_size * 100
        if total_original_size > 0 else 0
    )

    # ------------------------------------------
    # 運算效率
    # ------------------------------------------
    total_read_time = sum(
        item["read_time"] for item in previews
    )

    total_decompress_time = sum(
        item["decompress_time"] for item in previews
    )

    average_read_time = (
        total_read_time / file_count
        if file_count > 0 else 0
    )

    average_decompress_time = (
        total_decompress_time / file_count
        if file_count > 0 else 0
    )

    # ------------------------------------------
    # 整體統計資料
    # 尚未進行的測試先預設為 0
    # ------------------------------------------
    summary = {

        "file_count": file_count,

        # 儲存效率
        "total_original_size": total_original_size,
        "total_stored_size": total_stored_size,
        "total_saved_size": total_saved_size,
        "compression_ratio": compression_ratio,
        "saving_rate": saving_rate,

        # 運算效率
        

        "total_decompress_time": total_decompress_time,
        "average_decompress_time": average_decompress_time,

        "total_read_time": total_read_time,
        "average_read_time": average_read_time,

        # 服務延遲
        "average_latency": 0,
        "p95_latency": 0,

        # 處理能力
        "rps": 0,
        "throughput": 0,
        "success_requests": 0,
        "failed_requests": 0,
        "transferred_bytes": 0
    }

    # ==================================================
    # 7. 回傳網頁
    # ==================================================
    return templates.TemplateResponse(
        request=request,
        name="preview.html",
        context={
            "method": method,
            "previews": previews,
            "summary": summary
        }
    )