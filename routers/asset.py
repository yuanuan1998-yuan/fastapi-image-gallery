"""用户资产接口：收藏与下载记录的增删查。全部需要登录（Bearer Token）。

前缀 /api/asset：
  POST   /favorite          收藏某图
  DELETE /favorite/{id}     取消收藏
  GET    /favorite/status/{id}  是否已收藏
  GET    /favorite/count        收藏总数
  GET    /favorite/list         分页收藏列表（返回图片）
  POST   /download          记录一次下载
  GET    /download/count        下载总数
  GET    /download/list          分页下载列表（返回图片）
"""
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from utils.response import success_response
from utils.media import to_full_url
from crud import user_assets as assets
from config.db_conf import get_db
from models.users import User
from utils.wx_auth import get_current_user

router = APIRouter(prefix="/api/asset", tags=["user-assets"])


class ImageIdBody(BaseModel):
    image_id: int


def image_to_dict(image, request: Request, category_name=None) -> dict:
    base = str(request.base_url)
    data = {
        "id": image.id,
        "title": image.title,
        "url": to_full_url(image.url, base),
        "category_id": image.category_id,
        "file_size": image.file_size,
        "created_at": image.created_at,
        "updated_at": image.updated_at,
    }
    if category_name is not None:
        data["category_name"] = category_name
    return data


# ------------------------------------------------------------ 收藏
@router.post("/favorite")
async def add_favorite(
    body: ImageIdBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    added = await assets.add_favorite(db, current_user.id, body.image_id)
    return success_response("已收藏" if added else "已收藏过", data={"faved": True})


@router.delete("/favorite/{image_id}")
async def remove_favorite(
    image_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assets.remove_favorite(db, current_user.id, image_id)
    return success_response("已取消收藏", data={"faved": False})


@router.get("/favorite/status/{image_id}")
async def favorite_status(
    image_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    faved = await assets.is_favorite(db, current_user.id, image_id)
    return success_response("查询成功", data={"faved": faved})


@router.get("/favorite/count")
async def favorite_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success_response("查询成功", data={"count": await assets.count_favorites(db, current_user.id)})


@router.get("/favorite/list")
async def favorite_list(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await assets.list_favorites(db, current_user.id, page, page_size)
    result["items"] = [
        image_to_dict(item["image"], request, category_name=item["category_name"])
        for item in result["items"]
    ]
    return success_response("查询成功", data=result)


# ------------------------------------------------------------ 下载记录
@router.post("/download")
async def add_download(
    body: ImageIdBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assets.add_download(db, current_user.id, body.image_id)
    return success_response("已记录下载", data={"ok": True})


@router.get("/download/count")
async def download_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success_response("查询成功", data={"count": await assets.count_downloads(db, current_user.id)})


@router.get("/download/list")
async def download_list(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await assets.list_downloads(db, current_user.id, page, page_size)
    result["items"] = [
        image_to_dict(item["image"], request, category_name=item["category_name"])
        for item in result["items"]
    ]
    return success_response("查询成功", data=result)
