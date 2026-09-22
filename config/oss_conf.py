"""S3 兼容对象存储配置（Bitiful / 阿里云 OSS / 腾讯云 COS 等通用 S3 接口）。

全部通过环境变量配置，绝不把密钥写死在代码里。以下为 Bitiful（anyfast 存储桶）的示例值，
请在「缤纷云控制台 → S3 兼容接入」页面复制你自己的 Endpoint / AccessKey / 外链域名后回填。

本地开发：把变量写进项目根目录的 .env（已被 .gitignore 忽略，不会提交）。
线上部署（PythonAnywhere 等）：在运行环境的环境变量里设置，不要提交 .env。

开关说明：
  OSS_ENABLED=false（默认）→ 仍用原来的本地 uploads/ 目录，完全兼容旧部署；
  OSS_ENABLED=true        → 上传/删除走对象存储，数据库只存 object key。
"""
import os

# 最先执行：如果装了 python-dotenv，就自动加载项目根目录的 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _flag(val: str, default: bool = False) -> bool:
    return os.getenv(val, "false" if not default else "true").strip().lower() in ("1", "true", "yes", "on")


# 是否启用对象存储（默认关，保持本地存储行为）
OSS_ENABLED = _flag("OSS_ENABLED", default=False)

# S3 接入点（缤纷云官方为 https://s3.bitiful.net，注意是 .net 不是 .com）
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "https://s3.bitiful.net").strip()

# 鉴权（务必用环境变量/部署变量注入，不要硬编码）
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "").strip()
OSS_SECRET_ACCESS_KEY = os.getenv("OSS_SECRET_ACCESS_KEY", "").strip()

# 存储桶名称
OSS_BUCKET = os.getenv("OSS_BUCKET", "anyfast").strip()

# 区域（部分 S3 兼容服务可不填，留空即可）
OSS_REGION = os.getenv("OSS_REGION", "cn-east-1").strip() or None

# 公网访问域名：前端 <img src> 实际请求的地址（如 https://anyfast.bitiful.com）
OSS_PUBLIC_BASE = os.getenv("OSS_PUBLIC_BASE", "https://anyfast.s3.bitiful.net").strip().rstrip("/")

# 对象 key 前缀（区分本地旧数据），数据库里 S3 图片的 url 形如 images/<uuid>.jpg
OSS_KEY_PREFIX = os.getenv("OSS_KEY_PREFIX", "images/").strip()
if OSS_KEY_PREFIX and not OSS_KEY_PREFIX.endswith("/"):
    OSS_KEY_PREFIX += "/"

# 寻址风格：path（默认，兼容性最好）/ virtual / auto
OSS_ADDRESSING = os.getenv("OSS_ADDRESSING", "path").strip() or "path"


def require_oss_conf():
    """真正要上传前校验配置，缺失给出明确提示而不是让 S3 返回一个看不懂的报错。"""
    missing = [n for n, v in
               (("OSS_ACCESS_KEY_ID", OSS_ACCESS_KEY_ID),
                ("OSS_SECRET_ACCESS_KEY", OSS_SECRET_ACCESS_KEY)) if not v]
    if missing:
        raise RuntimeError(
            "未配置对象存储密钥：" + ", ".join(missing) +
            "。请设置环境变量 OSS_ACCESS_KEY_ID / OSS_SECRET_ACCESS_KEY，"
            "或写入项目根目录 .env。Bitiful 控制台『密钥管理』可获取。"
        )
