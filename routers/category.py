from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from utils.response import success_response
from utils.media import to_full_url
from utils.admin_auth import get_current_admin
from utils.cache import cached, cache
from crud import category
from schemas.category import CategoryCreate, CategoryUpdate
from config.db_conf import get_db

reouter = APIRouter(prefix="/api/category", tags=["category"])


def _fill_cover_url(data: dict | list, request: Request):
    """把记录中的相对封面路径补成完整 URL（外链原样保留）"""
    base = str(request.base_url)
    if isinstance(data, list):
        for item in data:
            item["cover_url"] = to_full_url(item.get("cover_url", ""), base)
    else:
        data["cover_url"] = to_full_url(data.get("cover_url", ""), base)
    return data


async def _invalidate_category_caches():
    """分类增删改后必须失效相关缓存，否则列表页 5 分钟内还是旧数据。
    分类列表带 image_count，分类下的图片列表/搜索结果也受影响，一并清掉。"""
    await cache.invalidate_prefix("category_list")
    await cache.invalidate_prefix("image_list")
    await cache.invalidate_prefix("image_search")


# 查询分类列表（公开接口）
@reouter.get("/list")
@cached(ttl=300, prefix="category_list")  # 分类变更不频繁，缓存 5 分钟
async def get_category_list(request: Request, db: AsyncSession = Depends(get_db)):
    category_list = await category.get_create_list(db)
    return success_response('查询分类列表成功', data=_fill_cover_url(category_list, request))


# 新增分类（需登录）
@reouter.post("/add")
async def add_category(
    category_data: CategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    new_category = await category.add_category_list(db, category_data)
    await _invalidate_category_caches()
    data = _fill_cover_url({
        "id": new_category.id,
        "name": new_category.name,
        "sort_order": new_category.sort_order,
        "cover_url": new_category.cover_url,
        "created_at": new_category.created_at,
        "updated_at": new_category.updated_at,
    }, request)
    return success_response('新增分类成功', data=data)


# 编辑分类（需登录）
@reouter.put("/update/{category_id}")
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    updated = await category.update_category_list(db, category_id, category_data)
    await _invalidate_category_caches()
    data = _fill_cover_url({
        "id": updated.id,
        "name": updated.name,
        "sort_order": updated.sort_order,
        "cover_url": updated.cover_url,
        "created_at": updated.created_at,
        "updated_at": updated.updated_at,
    }, request)
    return success_response('编辑分类成功', data=data)


# 删除分类（需登录；分类下仍有图片时会被拒绝）
@reouter.delete("/delete/{category_id}")
async def delete_category(
    category_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    deleted_category = await category.delete_category_list(db, category_id)
    await _invalidate_category_caches()
    return success_response('删除分类成功', data=_fill_cover_url(deleted_category, request))
