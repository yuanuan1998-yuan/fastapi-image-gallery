"""图片地址处理：数据库统一存相对路径（/static/xxx.png 或 S3 的 images/xxx.png）或外链地址，
返回前端时动态拼成完整 URL。"""
import re

from config.oss_conf import OSS_ENABLED, OSS_PUBLIC_BASE, OSS_KEY_PREFIX

# 匹配 http(s)://域名/static/... 中的路径部分
_FULL_STATIC_URL = re.compile(r"^https?://[^/]+(/static/.+)$")


def to_relative(url: str | None) -> str:
    """前端传回来的完整地址（如 http://host/static/a.png）转回相对路径再入库；
    外链地址（http://其他域名/...）和相对路径原样保留。"""
    if not url:
        return ""
    url = url.strip()
    m = _FULL_STATIC_URL.match(url)
    return m.group(1) if m else url


def to_full_url(url: str | None, base_url: str) -> str:
    """把相对路径拼成完整地址；外链和空值原样返回。

    开启 OSS 后：以 OSS_KEY_PREFIX 开头的 key（如 images/xxx.jpg）走对象存储公网域名；
    其余（/static/... 本地旧文件）仍走本服务域名，保证旧数据可读。
    """
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if OSS_ENABLED and OSS_PUBLIC_BASE and url.startswith(OSS_KEY_PREFIX):
        return OSS_PUBLIC_BASE.rstrip("/") + "/" + url.lstrip("/")
    return base_url.rstrip("/") + url


# ---------- 图片压缩 ----------

# 压缩阈值：超过这个大小或宽度才压
_MAX_WIDTH = 1920          # 超过这个宽度等比缩放
_SIZE_THRESHOLD = 300 * 1024  # 300KB 以下不压缩，省 CPU
_JPEG_QUALITY = 80         # JPEG 输出质量 1-100，80 肉眼几乎无损
# 不压缩的格式（动图 / 带透明通道的），压了会丢帧或丢透明
_SKIP_FORMATS = {"GIF", "WEBP", "PNG_TRANSPARENT"}


def compress_image(content: bytes, original_ext: str = "") -> tuple[bytes, str, int]:
    """智能压缩图片：
    - 小图 / 动图 / 透明图 → 原样返回
    - 大图 → 等比缩放到 ≤1920px 宽 + 转 JPEG quality=80
    返回：(压缩后内容, 扩展名不带点如 'jpg', 文件大小字节数)。
    """
    # 延迟导入：没装 Pillow 时不影响其他 URL 工具函数
    try:
        from PIL import Image
        import io
    except ImportError:
        return content, (original_ext.lstrip(".") if original_ext else "bin"), len(content)

    original_size = len(content)

    # ① 不够大，不值得压
    if original_size < _SIZE_THRESHOLD:
        return content, (original_ext.lstrip(".") if original_ext else "bin"), original_size

    try:
        img = Image.open(io.BytesIO(content))
        img_format = img.format or ""
        width, height = img.size
    except Exception:
        # Pillow 打不开（可能是损坏文件），放弃压缩
        return content, (original_ext.lstrip(".") if original_ext else "bin"), original_size

    # ② 动图 GIF → 跳过（压缩后丢帧）
    if img_format.upper() == "GIF":
        return content, (original_ext.lstrip(".") if original_ext else "gif"), original_size

    # ③ 透明图（PNG alpha / RGBA WebP）→ 跳过（转 JPEG 会丢透明）
    has_alpha = img.mode in ("RGBA", "LA", "P") and img.info.get("transparency") is not None
    # PNG 带 alpha 通道的另一种检测
    if img.mode == "RGBA":
        has_alpha = True
    if has_alpha:
        return content, (original_ext.lstrip(".") if original_ext else img_format.lower() or "png"), original_size

    # ④ 尺寸本身不大，只压质量就好（不缩放）
    need_resize = width > _MAX_WIDTH

    # 转 RGB（去掉任何残留的 alpha / palette）
    if img.mode != "RGB":
        # 合成白底（防止透明背景变黑）
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = bg

    if need_resize:
        ratio = _MAX_WIDTH / width
        new_size = (_MAX_WIDTH, max(1, int(height * ratio)))
        img = img.resize(new_size, Image.LANCZOS)

    # 重新编码为 JPEG quality=80
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    new_bytes = out.getvalue()

    # 如果压缩后反而变大（原图已经是 JPEG 且质量很高），放弃压缩
    if len(new_bytes) >= original_size:
        return content, (original_ext.lstrip(".") if original_ext else img_format.lower() or "bin"), original_size

    return new_bytes, "jpg", len(new_bytes)
