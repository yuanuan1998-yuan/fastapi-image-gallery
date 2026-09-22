import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from models.users import User
from schemas.users import UserRequest
from fastapi import HTTPException, status


#
# 注册用户
async def put_user(db: AsyncSession, user_data: UserRequest):
    # 1. 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在,请重新注册")

    # 2. 创建用户并交由 get_db() 依赖统一 commit
    user = User(username=user_data.username, password=user_data.password)
    db.add(user)
    await db.flush()  # 把 SQL 刷到数据库（不提交），让 id 生成出来
    await db.refresh(user)  # 读回最新字段
    return user

# 根据用户名查询用户资料
async def get_user(db: AsyncSession, user_name: str):
    query = select(User).where(User.username == user_name)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user

# 用户登录
async def poat_user_login(db: AsyncSession, username: str, password: str):
    query = select(User).where(User.username == username, User.password == password)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户名或密码错误")
    return user

# 删除用户
async def delete_user(db: AsyncSession, user_data: UserRequest):
    # 1. 检查用户是否存在（get_user 查不到时内部已抛 404）
    user = await get_user(db, user_data.username)
    # 2. 校验密码
    if user.password != user_data.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='用户密码错误')
    # 3. 删除前先快照用户信息（删除提交后该行已不存在，无法再查询）
    deleted_user = {
        'id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'avatar': user.avatar,
        'gender': user.gender,
        'bio': user.bio,
        'phone': user.phone,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
    }
    # 4. 执行删除并提交
    stmt = delete(User).where(User.id == user.id)
    await db.execute(stmt)
    await db.commit()
    # 5. 返回被删除的用户信息
    return deleted_user


# ============================================================ 微信小程序登录
def user_public_dict(user: User) -> dict:
    """返回给小程序的安全字段（不含 password / openid）"""
    return {
        'id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'avatar': user.avatar,
        'gender': user.gender,
        'bio': user.bio,
        'phone': user.phone,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
    }


# 根据 openid 查询微信用户
async def get_user_by_openid(db: AsyncSession, openid: str):
    result = await db.execute(select(User).where(User.openid == openid))
    return result.scalar_one_or_none()


# 微信一键登录：openid 已存在则直接返回，不存在则自动注册
async def get_or_create_wx_user(
    db: AsyncSession,
    openid: str,
    nickname: str = None,
    avatar: str = None,
):
    user = await get_user_by_openid(db, openid)
    if user is not None:
        # 已注册：只有传了资料才覆盖，避免把已有昵称清掉
        if nickname:
            user.nickname = nickname
        if avatar:
            user.avatar = avatar
        await db.flush()
        return user, False

    user = User(
        # username 在表里是 NOT NULL 且唯一，微信用户用 openid 尾段兜底生成
        username=f"wx_{openid[-12:]}",
        password=f"wx-oauth-{secrets.token_hex(16)}",  # 微信用户不走密码登录，仅占位
        openid=openid,
        nickname=nickname or f"微信用户{openid[-4:]}",
        avatar=avatar,
    )
    db.add(user)
    await db.flush()      # 把 SQL 刷到数据库（不提交），让 id 生成出来
    await db.refresh(user)
    return user, True


# 绑定手机号（手机号一键登录）
async def bind_user_phone(db: AsyncSession, user: User, phone: str):
    # 该手机号若已被别的账号占用，直接拒绝
    result = await db.execute(
        select(User).where(User.phone == phone, User.id != user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该手机号已被其他账号绑定")
    user.phone = phone
    await db.flush()
    await db.refresh(user)
    return user


# 更新微信用户资料
async def update_wx_profile(db: AsyncSession, user: User, nickname: str = None, avatar: str = None):
    if nickname:
        user.nickname = nickname
    if avatar:
        user.avatar = avatar
    await db.flush()
    await db.refresh(user)
    return user
















