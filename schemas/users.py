from typing import Optional

from pydantic import BaseModel


class UserRequest(BaseModel):
    username: str
    password: str


class WxLoginRequest(BaseModel):
    """微信小程序一键登录入参
    code 为 wx.login() 拿到的临时凭证（5 分钟有效、只能用一次）
    nickname / avatar 可选：小程序端用 <button open-type="chooseAvatar"> 等方式拿到后一起提交
    """
    code: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class WxPhoneRequest(BaseModel):
    """手机号一键绑定入参：code 来自 <button open-type="getPhoneNumber"> 回调"""
    code: str


class WxProfileRequest(BaseModel):
    """更新微信用户资料"""
    nickname: Optional[str] = None
    avatar: Optional[str] = None
