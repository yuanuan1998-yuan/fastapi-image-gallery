import os

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud import admin as admin_crud
from models.admin import Admin
from schemas.admin import AdminLogin, AdminCreate, PasswordChange
from utils.admin_auth import create_token, get_current_admin
from utils.response import success_response
from utils.media import to_full_url
from utils.s3 import store_image

reouter = APIRouter(prefix="/api/admin", tags=["admin"])

# 封面等通用文件上传的配置（实际存哪由 store_image 根据 OSS 开关决定）
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MAX_SIZE = 10 * 1024 * 1024
# 封面在对象存储里的子目录（key 形如 images/covers/xxx.png）
COVER_SUBDIR = "covers/"


# 管理员登录（无需登录态）
@reouter.post("/login")
async def login(data: AdminLogin, db: AsyncSession = Depends(get_db)):
    admin = await admin_crud.authenticate(db, data.username, data.password)
    token = create_token(admin.id, admin.username)
    return success_response('登录成功', data={
        "token": token,
        "id": admin.id,
        "username": admin.username,
    })


# 获取当前登录管理员信息
@reouter.get("/info")
async def admin_info(admin: Admin = Depends(get_current_admin)):
    return success_response('获取成功', data={"id": admin.id, "username": admin.username})


# 管理员列表
@reouter.get("/list")
async def admin_list(
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return success_response('查询管理员列表成功', data=await admin_crud.get_admin_list(db))


# 新增管理员
@reouter.post("/add")
async def add_admin(
    data: AdminCreate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return success_response('新增管理员成功', data=await admin_crud.add_admin(db, data))


# 修改密码
@reouter.put("/password")
async def change_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    await admin_crud.change_password(db, admin, data)
    return success_response('密码修改成功')


# 删除管理员
@reouter.delete("/{admin_id}")
async def delete_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return success_response('删除管理员成功', data=await admin_crud.delete_admin(db, admin, admin_id))


# 通用文件上传（用于分类封面等场景）：只存文件返回 URL，不写图片表
@reouter.post("/upload-file")
async def upload_file(
    request: Request,
    file: UploadFile = File(..., description="图片文件"),
    admin: Admin = Depends(get_current_admin),
):
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的图片格式")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传的文件不是图片类型")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传的文件为空")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片大小不能超过 10MB")

    # OSS 开启时上传到对象存储并返回 object key，否则存本地 uploads 返回 /static/...
    relative_url = await store_image(content, ext, COVER_SUBDIR)
    return success_response('上传成功', data={
        "url": to_full_url(relative_url, str(request.base_url)),
        "relative_url": relative_url,
        "file_size": len(content),
    })
