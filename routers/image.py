from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from utils.response import success_response
from utils.media import to_full_url
from utils.admin_auth import get_current_admin
from utils.cache import cached, cache
from crud import image as image_crud
from schemas.image import ImageUpdate
from config.db_conf import get_db

reouter = APIRouter(prefix="/api/image", tags=["image"])


# 把 ORM 对象转成字典（相对路径拼成完整 URL）
def image_to_dict(image, request: Request, category_name: str | None = None) -> dict:
    base = str(request.base_url)
    data = {
        "id": image.id,
        "title": image.title,
        "url": to_full_url(image.url, base),     # 完整图片地址，前端 <img src> 可直接用
        "category_id": image.category_id,
        "file_size": image.file_size,
        "created_at": image.created_at,
        "updated_at": image.updated_at,
    }
    if category_name is not None:
        data["category_name"] = category_name
    return data


async def _invalidate_all_image_caches():
    """写操作后统一失效所有图片/分类相关缓存。"""
    await cache.invalidate_prefix("image_list")
    await cache.invalidate_prefix("image_search")
    await cache.invalidate_prefix("image_detail")
    await cache.invalidate_prefix("category_list")  # 分类列表里有 image_count，也得刷新


# 上传图片（需登录；multipart/form-data：file + category_name + 可选 title）
@reouter.post("/upload")
async def upload_image(
    request: Request,
    file: UploadFile = File(..., description="图片文件"),
    category_name: str = Form(..., description="分类名称（需已存在）"),
    title: str | None = Form(default=None, description="图片标题，不传则用原文件名"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    image = await image_crud.upload_image(db, category_name, file, title)
    await _invalidate_all_image_caches()
    return success_response('上传图片成功', data=image_to_dict(image, request))


# 批量上传（需登录；多文件 + 统一分类名，单张失败不影响其他图片）
@reouter.post("/batch-upload")
async def batch_upload_images(
    request: Request,
    files: list[UploadFile] = File(..., description="多张图片文件"),
    category_name: str = Form(..., description="统一归入的分类名称（需已存在）"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await image_crud.batch_upload_images(db, category_name, files)
    base = str(request.base_url)
    # 成功记录里的相对路径补成完整 URL
    for item in result["success"]:
        item["url"] = to_full_url(item["url"], base)
    await _invalidate_all_image_caches()
    return success_response(
        f"批量上传完成：成功{result['success_count']}张，失败{result['failed_count']}张",
        data=result,
    )


# 图片列表（公开；可按分类名筛选 + 分页）
# 注意：/list 必须定义在 /{image_id} 之前
@reouter.get("/list")
@cached(ttl=60, prefix="image_list")  # 列表变化相对频繁，缓存 1 分钟
async def get_image_list(
    request: Request,
    category_name: str | None = Query(default=None, description="分类名称，不传则查全部分类"),
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，1-100"),
    db: AsyncSession = Depends(get_db),
):
    result = await image_crud.get_image_list(db, category_name, page, page_size)
    result["items"] = [
        image_to_dict(item["image"], request, category_name=item["category_name"])
        for item in result["items"]
    ]
    return success_response('查询图片列表成功', data=result)


# 搜索图片（公开）：关键词模糊匹配图片标题/分类名，或按图片ID精确搜索
@reouter.get("/search")
@cached(ttl=60, prefix="image_search")  # 搜索结果缓存 1 分钟
async def search_images(
    request: Request,
    keyword: str | None = Query(default=None, description="关键词：同时模糊匹配图片标题和分类名称"),
    image_id: int | None = Query(default=None, gt=0, description="图片ID，传入则精确查找"),
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，1-100"),
    db: AsyncSession = Depends(get_db),
):
    result = await image_crud.search_images(db, keyword, image_id, page, page_size)
    result["items"] = [
        image_to_dict(item["image"], request, category_name=item["category_name"])
        for item in result["items"]
    ]
    return success_response('搜索图片成功', data=result)


# 批量删除图片（需登录；同步删除 S3 文件）
@reouter.post("/batch-delete")
async def batch_delete_images(
    image_ids: list[int],
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await image_crud.batch_delete_images(db, image_ids)
    await _invalidate_all_image_caches()
    return success_response(
        f"批量删除完成：成功{result['success_count']}张，失败{result['failed_count']}张",
        data=result,
    )


# 图片详情（公开；附带所属分类名称和分类封面）
@reouter.get("/{image_id}")
@cached(ttl=120, prefix="image_detail")  # 单张图片详情缓存 2 分钟
async def get_image(image_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = await image_crud.get_image(db, image_id)
    data = image_to_dict(result["image"], request, category_name=result["category_name"])
    data["category_cover"] = to_full_url(result["category_cover"], str(request.base_url))
    return success_response('查询图片详情成功', data=data)


# 编辑图片（需登录；改标题/调整分类）
@reouter.put("/update/{image_id}")
async def update_image(
    image_id: int,
    body: ImageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    image = await image_crud.update_image(db, image_id, body.title, body.category_name)
    await _invalidate_all_image_caches()
    return success_response('编辑图片成功', data=image_to_dict(image, request))


# 删除图片（需登录；同时删除本地文件）
@reouter.delete("/{image_id}")
async def delete_image(
    image_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await image_crud.delete_image(db, image_id)
    result["url"] = to_full_url(result["url"], str(request.base_url))
    await _invalidate_all_image_caches()
    return success_response('删除图片成功', data=result)
