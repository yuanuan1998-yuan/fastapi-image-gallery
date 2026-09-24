import os

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.admin import Admin
from schemas.admin import AdminCreate, PasswordChange
from utils.admin_auth import hash_password, verify_password

def _default_admin_credentials() -> tuple[str, str]:
    """初始管理员账号密码：优先读环境变量，没配才用默认值。
    上线前建议用 ADMIN_USERNAME / ADMIN_PASSWORD 改成自己的账号密码。"""
    username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    return username, password


# 启动时调用：数据库里已有该账号 → 跳过；不存在 → 创建
# 只做初始化，不会重复创建，也不会重置已有账号的密码
async def ensure_default_admin(db: AsyncSession) -> dict:
    username, password = _default_admin_credentials()
    exists = (
        await db.execute(select(Admin).where(Admin.username == username))
    ).scalar_one_or_none()
    if exists is not None:
        return {"created": False, "username": username}

    db.add(Admin(username=username, password=hash_password(password)))
    await db.commit()
    return {"created": True, "username": username}


# 登录校验，成功返回管理员对象
async def authenticate(db: AsyncSession, username: str, password: str) -> Admin:
    admin = (
        await db.execute(select(Admin).where(Admin.username == username))
    ).scalar_one_or_none()
    # 账号不存在或密码错误统一提示，避免泄露账号是否存在
    if admin is None or not verify_password(password, admin.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    return admin


# 管理员列表（不返回密码哈希）
async def get_admin_list(db: AsyncSession):
    admins = (await db.execute(select(Admin).order_by(Admin.id))).scalars().all()
    return [
        {"id": a.id, "username": a.username, "created_at": a.created_at}
        for a in admins
    ]


# 新增管理员
async def add_admin(db: AsyncSession, data: AdminCreate) -> dict:
    exists = (
        await db.execute(select(Admin).where(Admin.username == data.username))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="管理员账号已存在")

    admin = Admin(username=data.username, password=hash_password(data.password))
    db.add(admin)
    await db.flush()
    await db.commit()
    # created_at 是数据库生成的列，commit 后需显式异步刷新，否则同步访问会触发懒加载报错
    await db.refresh(admin)
    return {"id": admin.id, "username": admin.username, "created_at": admin.created_at}


# 修改自己的密码
async def change_password(db: AsyncSession, admin: Admin, data: PasswordChange):
    if not verify_password(data.old_password, admin.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    if verify_password(data.new_password, admin.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与原密码相同")

    admin.password = hash_password(data.new_password)
    await db.commit()
    return True


# 删除管理员（不允许删除自己；至少保留一个管理员）
async def delete_admin(db: AsyncSession, current_admin: Admin, admin_id: int):
    if admin_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号")

    target = await db.get(Admin, admin_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="管理员不存在")

    total = (await db.execute(select(func.count()).select_from(Admin))).scalar()
    if total <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少保留一个管理员")

    info = {"id": target.id, "username": target.username}
    await db.delete(target)
    await db.commit()
    return info
