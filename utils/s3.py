"""S3 兼容对象存储客户端（Bitiful 等通用 S3 接口）。

boto3 采用「延迟导入」：未安装 boto3 时模块仍可正常 import，
本地存储模式（OSS_ENABLED=false）不受影响；只有真正开启 OSS 上传才会去 import boto3。

对外统一入口是 store_image()：
  - OSS_ENABLED=true  → 上传到对象存储，返回 object key（如 images/covers/xxx.jpg）
  - OSS_ENABLED=false → 回退到本地 uploads/ 目录，返回 /static/...（保持原行为）
两种模式返回值语义一致，业务层无需关心底层存哪。
"""
import asyncio
import os
import uuid

from config.oss_conf import (
    OSS_ENABLED, OSS_ENDPOINT, OSS_ACCESS_KEY_ID, OSS_SECRET_ACCESS_KEY,
    OSS_BUCKET, OSS_REGION, OSS_ADDRESSING, OSS_KEY_PREFIX,
)

# 本地回退模式的存储根目录（项目根/uploads，与 main.py 挂载的 /static 对应）
STORE_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
LOCAL_URL_PREFIX = "/static"

_CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}


def _make_client():
    # 延迟导入：没装 boto3 时不影响本地存储模式启动
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=OSS_ENDPOINT or None,
        aws_access_key_id=OSS_ACCESS_KEY_ID or None,
        aws_secret_access_key=OSS_SECRET_ACCESS_KEY or None,
        region_name=OSS_REGION,
        config=Config(s3={"addressing_style": OSS_ADDRESSING or "path"}),
    )


def _upload(key: str, data: bytes, content_type: str | None = None):
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    _make_client().put_object(Bucket=OSS_BUCKET, Key=key, Body=data, **extra)


def _delete(key: str):
    _make_client().delete_object(Bucket=OSS_BUCKET, Key=key)


def _exists(key: str) -> bool:
    try:
        _make_client().head_object(Bucket=OSS_BUCKET, Key=key)
        return True
    except Exception:
        return False


async def upload_object(key: str, data: bytes, content_type: str | None = None):
    """异步上传一个对象到对象存储。"""
    await asyncio.to_thread(_upload, key, data, content_type)


async def delete_object(key: str):
    """异步删除一个对象（失败静默，不影响接口返回）。"""
    await asyncio.to_thread(_delete, key)


async def object_exists(key: str) -> bool:
    """异步判断对象是否存在。"""
    return await asyncio.to_thread(_exists, key)


def _generate_presigned_url(key: str, expires: int = 604800) -> str:
    """生成预签名 URL（默认 7 天有效期）。"""
    return _make_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": OSS_BUCKET, "Key": key},
        ExpiresIn=expires,
    )


async def generate_presigned_url(key: str, expires: int = 604800) -> str:
    """异步生成预签名 URL（默认 7 天有效期）。"""
    return await asyncio.to_thread(_generate_presigned_url, key, expires)


async def store_image(content: bytes, ext: str, subdir: str = "") -> str:
    """保存一张图片，返回应写入数据库的 URL（OSS 模式下是 object key，本地模式是 /static/...）。

    ext    : 扩展名，可带点也可不带点，如 '.png' 或 'png'
    subdir : 对象 key 里的子目录，如 covers/、banners/，用于区分不同业务场景
    """
    ext = (ext or "").lstrip(".").lower()
    if subdir and not subdir.endswith("/"):
        subdir += "/"
    name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")

    if OSS_ENABLED:
        from config.oss_conf import require_oss_conf
        require_oss_conf()
        key = f"{OSS_KEY_PREFIX}{subdir}{name}"
        await upload_object(key, content, content_type)
        return key

    # 未开启 OSS：沿用原来的本地存储方式
    local_dir = os.path.join(STORE_ROOT, subdir)
    os.makedirs(local_dir, exist_ok=True)
    with open(os.path.join(local_dir, name), "wb") as f:
        f.write(content)
    return f"{LOCAL_URL_PREFIX}/{subdir}{name}"
