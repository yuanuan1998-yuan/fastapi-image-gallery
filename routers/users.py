
from fastapi import APIRouter, Depends , HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from utils.response import success_response
from crud import users
from schemas.users import UserRequest, WxLoginRequest, WxPhoneRequest, WxProfileRequest
from config.db_conf import get_db
from utils.wx_auth import (
    code2session,
    get_phone_number,
    create_user_token,
    get_current_user,
)
from models.users import User
reouter = APIRouter(prefix="/api/user", tags=["user"])


# 注册用户
@reouter.post("/register")
async def put_user(user_data: UserRequest,db : AsyncSession = Depends(get_db)):
    result = await users.put_user(db,user_data)

    return success_response('注册成功',data=result)


# ---------------------------------------------------------------- 微信小程序登录
# 一键登录：wx.login() -> code -> openid -> 查/建用户 -> 下发 token
@reouter.post("/wxlogin")
async def wx_login(wx_data: WxLoginRequest, db: AsyncSession = Depends(get_db)):
    session = await code2session(wx_data.code)      # 拿 openid（失败会抛 400）
    openid = session["openid"]
    user, created = await users.get_or_create_wx_user(
        db, openid, wx_data.nickname, wx_data.avatar
    )
    token = create_user_token(user.id, openid)
    return success_response(
        '首次登录，已自动注册' if created else '登录成功',
        data={'token': token, 'user': users.user_public_dict(user)},
    )


# 手机号一键绑定：<button open-type="getPhoneNumber"> 回调的 code -> 真实手机号
@reouter.post("/wxphone")
async def wx_bind_phone(
    phone_data: WxPhoneRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    phone = await get_phone_number(phone_data.code)
    user = await users.bind_user_phone(db, current_user, phone)
    return success_response('手机号绑定成功', data=users.user_public_dict(user))


# 当前登录用户（必须放在 /{user_name} 之前，否则会被当成 user_name="me" 匹配掉）
@reouter.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return success_response('查询成功', data=users.user_public_dict(current_user))


# 更新当前用户资料
@reouter.put("/profile")
async def update_profile(
    profile: WxProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await users.update_wx_profile(db, current_user, profile.nickname, profile.avatar)
    return success_response('资料更新成功', data=users.user_public_dict(user))


# 根据用户ID查询用户资料
@reouter.get("/{user_name}")
async def get_user(user_name: str, db: AsyncSession = Depends(get_db)):
    result = await users.get_user(db, user_name=user_name)
    return success_response('查询成功', data=result)


# 用户登录
@reouter.post("/login")
async def login_user(user_data: UserRequest,db : AsyncSession = Depends(get_db)):
    result = await users.poat_user_login(db,user_data.username,user_data.password)

    return success_response('登陆成功',data=result)

#删除用户
@reouter.delete("/delete")
async def delete_user(user_data: UserRequest, db: AsyncSession = Depends(get_db)):
    result = await users.delete_user(db, user_data)
    return success_response('注销成功', data=result)

