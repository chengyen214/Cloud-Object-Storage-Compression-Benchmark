from app.minio_client import client, BUCKET_NAME


def get_available_methods():
    """取得 MinIO 中目前存在的壓縮方式"""

    methods = set()

    objects = client.list_objects(
        BUCKET_NAME,
        recursive=True
    )

    for obj in objects:
        parts = obj.object_name.split("/")

        if len(parts) >= 2 and parts[0]:
            methods.add(parts[0])

    return sorted(methods)


def get_method_files(method):
    """取得指定壓縮方式底下的檔案"""

    files = []

    objects = client.list_objects(
        BUCKET_NAME,
        prefix=f"{method}/",
        recursive=True
    )

    for obj in objects:
        if obj.object_name.endswith("/"):
            continue

        files.append({
            "name": obj.object_name.split("/")[-1],
            "path": obj.object_name,
            "size": obj.size
        })

    return files