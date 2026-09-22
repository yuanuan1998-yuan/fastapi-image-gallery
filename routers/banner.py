import os

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from utils.response import success_response
from utils.media import to_full_url
from utils.admin_auth import get_current_admin
from utils.cache import cached, cache
from utils.s3 import store_image
from crud import banner as banner_crud
from schemas.banner import BannerCreate, BannerUpdate
from config.db_conf import get_db

reouter = APIRouter(prefix="/api/banner", tags=["banner"])

# 海报图片上传配置（实际存哪由 store_image 根据 OSS 开关决定）
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MAX_SIZE = 10 * 1024 * 1024
# 海报在对象存储里的子目录（key 形如 images/banners/xxx.jpg）
BANNER_SUBDIR = "banners/"


def _fill_url(data, request: Request):
    """记录中的相对图片路径补成完整 URL（外链原样保留）"""
    base = str(request.base_url)
    if isinstance(data, list):
        for item in data:
            item["image_url"] = to_full_url(item.get("image_url", ""), base)
    else:
        data["image_url"] = to_full_url(data.get("image_url", ""), base)
    return data


# 公开：首页轮播列表（仅返回启用的）
@reouter.get("/list")
@cached(ttl=300, prefix="banner_list")
async def list_banners(request: Request, db: AsyncSession = Depends(get_db)):
    data = await banner_crud.get_enabled_list(db)
    return success_response('获取轮播海报成功', data=_fill_url(data, request))


# 管理：全部海报（含停用），供后台编辑
@reouter.get("/admin/list")
async def admin_list_banners(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    data = await banner_crud.get_all(db)
    return success_response('获取海报列表成功', data=_fill_url(data, request))


# 管理：新增海报
@reouter.post("/add")
async def add_banner(
    data: BannerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    b = await banner_crud.create_banner(db, data)
    await cache.invalidate_prefix("banner_list")
    return success_response('添加海报成功', data=_fill_url(b, request))


# 管理：编辑海报
@reouter.put("/update/{banner_id}")
async def update_banner(
    banner_id: int,
    data: BannerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    b = await banner_crud.update_banner(db, banner_id, data)
    await cache.invalidate_prefix("banner_list")
    return success_response('更新海报成功', data=_fill_url(b, request))


# 管理：删除海报
@reouter.delete("/{banner_id}")
async def delete_banner(
    banner_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    info = await banner_crud.delete_banner(db, banner_id)
    await cache.invalidate_prefix("banner_list")
    return success_response('删除海报成功', data=_fill_url(info, request))


# 管理：上传海报图片，返回可直接入库的 URL（相对路径 + 完整路径）
@reouter.post("/upload")
async def upload_banner_image(
    request: Request,
    file: UploadFile = File(..., description="海报图片文件"),
    _admin=Depends(get_current_admin),
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
    relative_url = await store_image(content, ext, BANNER_SUBDIR)
    return success_response('上传成功', data={
        "url": to_full_url(relative_url, str(request.base_url)),
        "relative_url": relative_url,
        "file_size": len(content),
    })
