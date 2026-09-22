"""后台管理员鉴权工具：密码哈希、Token 签发/校验、登录态依赖。
全部使用 Python 标准库实现，无需额外依赖（学习项目方案，正式项目建议用 passlib+JWT）。"""
import base64
import hashlib
import hmac
import json
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from models.admin import Admin

# Token 签名密钥（学习项目固定值；生产环境应放到环境变量）
SECRET_KEY = "image-gallery-admin-secret-2026"
# Token 有效期 12 小时
TOKEN_EXPIRE_SECONDS = 12 * 60 * 60
# 密码哈希用的盐
_PASSWORD_SALT = "image-gallery-pwd-salt"

# Bearer Token 提取器（Swagger 文档右上角会出现 Authorize 按钮）
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """sha256(盐+密码)，数据库中绝不存明文密码"""
    return hashlib.sha256((_PASSWORD_SALT + password).encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def create_token(admin_id: int, username: str) -> str:
    """签发 token：base64(载荷).签名，载荷含管理员id、账号和过期时间"""
    payload = {"id": admin_id, "username": username, "exp": int(time.time()) + TOKEN_EXPIRE_SECONDS}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def parse_token(token: str) -> dict:
    """校验并解析 token，失败抛 401"""
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证格式错误")

    expected_sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效")

    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    return payload


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """接口依赖：校验请求头 Authorization: Bearer <token>，返回当前管理员对象"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    payload = parse_token(credentials.credentials)
    admin = await db.get(Admin, payload["id"])
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")
    return admin
