"""微信小程序配置：AppID 和 AppSecret。

获取方式：微信公众平台 https://mp.weixin.qq.com
  「开发管理 → 开发设置」里能看到 AppID(小程序ID) 和 AppSecret(小程序密钥)

建议用环境变量配置（不要写进代码提交到仓库）：
    set WX_APPID=wxXXXXXXXXXXXXXXXX
    set WX_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

开发模式（可选，强烈建议只在本地开）：
    set WX_DEV_MODE=1
    开启后后端不再请求微信服务器，用 WX_DEV_OPENID 这个固定 openid 直接放行，
    这样在还没申请到 AppID / 用测试号调试时，也能把「登录 -> token -> /me」整条链路跑通。
"""
import os


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# 小程序 AppID（已填好，也可继续用环境变量 WX_APPID 覆盖）
APPID = os.getenv("WX_APPID", "wxa3ecc01192fccf15")
# 小程序 AppSecret（已填好，也可继续用环境变量 WX_SECRET 覆盖）
SECRET = os.getenv("WX_SECRET", "acce01d973b36f1e4d8856995f4d3712")

# 开发模式开关：默认关闭
DEV_MODE = _env_flag("WX_DEV_MODE")
# 开发模式下使用的模拟身份（固定值，保证每次登录都是同一个账号）
DEV_OPENID = os.getenv("WX_DEV_OPENID", "dev-openid-0001")
DEV_PHONE = os.getenv("WX_DEV_PHONE", "13800138000")


def require_wx_conf():
    """接口调用前检查配置是否完整，没配就给出明确提示，而不是让微信返回一个看不懂的错误码"""
    if DEV_MODE:
        return APPID or "dev-appid", SECRET or "dev-secret"
    if not APPID or not SECRET:
        raise RuntimeError(
            "未配置微信小程序 AppID / AppSecret："
            "请设置环境变量 WX_APPID、WX_SECRET，或直接写在 config/wx_conf.py 中；"
            "本地调试也可临时 set WX_DEV_MODE=1 跳过微信服务器校验。"
        )
    return APPID, SECRET
