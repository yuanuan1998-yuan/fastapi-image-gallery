from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.admin import Admin
from schemas.admin import AdminCreate, PasswordChange
from utils.admin_auth import hash_password, verify_password

# 系统初始管理员：表中不存在 admin 账号时自动创建
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


# 启动时调用：确保默认管理员 admin/admin123 存在
async def ensure_default_admin(db: AsyncSession):
    exists = (
        await db.execute(select(Admin).where(Admin.username == DEFAULT_ADMIN_USERNAME))
    ).scalar_one_or_none()
    if exists is None:
        db.add(Admin(
            username=DEFAULT_ADMIN_USERNAME,
            password=hash_password(DEFAULT_ADMIN_PASSWORD),
        ))
        await db.commit()


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
