"""微信小程序登录鉴权：code2session、手机号一键获取、用户 Token 签发/校验。

HTTP 请求全部用标准库 urllib（不引入 httpx/requests 等新依赖），
因为是同步阻塞 IO，统一用 asyncio.to_thread 丢到线程池，避免卡住事件循环。

登录流程：
    小程序 wx.login()  ->  code
    后端 code2session   ->  openid + session_key
    按 openid 查/建用户  ->  签发自己的 token 返回给小程序
"""
import asyncio
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from config.wx_conf import require_wx_conf, DEV_MODE, DEV_OPENID, DEV_PHONE
from models.users import User

# 微信接口地址
JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
GET_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"

# 用户 Token 签名密钥（与管理端 admin_auth 分开，互不影响）
WX_TOKEN_SECRET = "image-gallery-wx-user-secret-2026"
# 小程序端登录态保留 30 天（小程序没有刷新 token 的入口，给长一点）
WX_TOKEN_EXPIRE_SECONDS = 30 * 24 * 60 * 60

# Bearer Token 提取器（auto_error=False：取不到时返回 None，由依赖自己抛错）
bearer_scheme = HTTPBearer(auto_error=False)

# access_token 缓存（微信限制每日获取次数，且 2 小时有效）
_access_token_cache = {"token": "", "expire_at": 0.0}


# ---------------------------------------------------------------- HTTP 小工具
def _http_get_json(url: str, timeout: int = 8) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict, timeout: int = 8) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- 微信接口
async def code2session(code: str) -> dict:
    """用 wx.login() 拿到的 code 换 openid + session_key（一键登录的核心）"""
    # 开发模式：不请求微信服务器，直接返回固定的 openid
    if DEV_MODE:
        return {"openid": DEV_OPENID, "session_key": "dev-session-key", "dev": True}

    appid, secret = require_wx_conf()
    params = urllib.parse.urlencode({
        "appid": appid,
        "secret": secret,
        "js_code": code,
        "grant_type": "authorization_code",
    })
    data = await asyncio.to_thread(_http_get_json, f"{JSCODE2SESSION_URL}?{params}")

    errcode = data.get("errcode", 0)
    if errcode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信登录失败({errcode})：{data.get('errmsg', '')}",
        )
    if not data.get("openid"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信登录失败：未取到 openid")
    return data


async def get_access_token() -> str:
    """获取小程序全局 access_token（带内存缓存，提前 60 秒过期）"""
    now = time.time()
    if _access_token_cache["token"] and _access_token_cache["expire_at"] > now + 60:
        return _access_token_cache["token"]

    appid, secret = require_wx_conf()
    params = urllib.parse.urlencode({
        "appid": appid,
        "secret": secret,
        "grant_type": "client_credential",
    })
    data = await asyncio.to_thread(_http_get_json, f"{ACCESS_TOKEN_URL}?{params}")
    token = data.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"获取 access_token 失败({data.get('errcode')})：{data.get('errmsg', '')}",
        )
    _access_token_cache["token"] = token
    _access_token_cache["expire_at"] = now + int(data.get("expires_in", 7200))
    return token


async def get_phone_number(code: str) -> str:
    """用 <button open-type="getPhoneNumber"> 回调里的 code 换真实手机号
    注意：个人主体小程序没有该接口权限，需要企业/个体工商户主体。"""
    if DEV_MODE:
        return DEV_PHONE

    token = await get_access_token()
    data = await asyncio.to_thread(
        _http_post_json, f"{GET_PHONE_URL}?access_token={token}", {"code": code}
    )
    if data.get("errcode"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"获取手机号失败({data.get('errcode')})：{data.get('errmsg', '')}",
        )
    phone_info = data.get("phone_info") or {}
    phone = phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber")
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未取到手机号")
    return phone


# ---------------------------------------------------------------- 用户 Token
def create_user_token(user_id: int, openid: str = "") -> str:
    """签发用户 token：base64(载荷).签名"""
    payload = {
        "id": user_id,
        "openid": openid,
        "type": "wx_user",
        "exp": int(time.time()) + WX_TOKEN_EXPIRE_SECONDS,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(WX_TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def parse_user_token(token: str) -> dict:
    """校验并解析用户 token，失败抛 401"""
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证格式错误")

    expected_sig = hmac.new(WX_TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效")

    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效")

    if payload.get("type") != "wx_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证类型错误")
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """接口依赖：校验 Authorization: Bearer <token>，返回当前小程序用户"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    payload = parse_user_token(credentials.credentials)
    user = await db.get(User, payload["id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")
    return user
