import sqlite3
from pathlib import Path
from datetime import datetime


# ==================================================
# 資料庫設定
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "operation_logs.db"


# ==================================================
# 建立資料庫與資料表
# ==================================================

def init_database():

    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operation_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            method TEXT NOT NULL,

            filename TEXT NOT NULL,

            data_type TEXT,

            original_size INTEGER,

            stored_size INTEGER,

            compression_ratio REAL,

            saving_rate REAL,

            compress_time REAL,

            decompress_time REAL,

            read_time REAL,

            status TEXT NOT NULL,

            error_message TEXT,

            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ==================================================
# 新增處理紀錄
# ==================================================

def add_log(
    method,
    filename,
    data_type=None,
    original_size=None,
    stored_size=None,
    compression_ratio=None,
    saving_rate=None,
    compress_time=None,
    decompress_time=None,
    read_time=None,
    status="success",
    error_message=None
):

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO operation_logs (
            method,
            filename,
            data_type,
            original_size,
            stored_size,
            compression_ratio,
            saving_rate,
            compress_time,
            decompress_time,
            read_time,
            status,
            error_message,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        method,
        filename,
        data_type,
        original_size,
        stored_size,
        compression_ratio,
        saving_rate,
        compress_time,
        decompress_time,
        read_time,
        status,
        error_message,
        datetime.now().isoformat(timespec="seconds")
    ))

    conn.commit()
    conn.close()


# ==================================================
# 查詢所有處理紀錄
# ==================================================

def get_all_logs():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM operation_logs
        ORDER BY id DESC
    """)

    logs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return logs


# ==================================================
# 查詢指定壓縮方式的紀錄
# ==================================================

def get_logs_by_method(method):

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM operation_logs
        WHERE method = ?
        ORDER BY id DESC
    """, (method,))

    logs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return logs


# ==================================================
# 刪除所有處理紀錄
# ==================================================

def clear_logs():

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("DELETE FROM operation_logs")

    conn.commit()
    conn.close()


# ==================================================
# 初始化資料庫
# ==================================================

if __name__ == "__main__":

    init_database()

    print("=" * 50)
    print("Operation Logger 資料庫初始化成功")
    print(f"資料庫位置：{DB_PATH}")
    print("=" * 50)