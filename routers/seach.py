from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from utils.response import success_response
from crud import image as image_crud
from config.db_conf import get_db
# 复用图片路由里统一的响应格式（相对路径拼完整 URL）
from routers.image import image_to_dict

reouter = APIRouter(prefix="/api/search", tags=["search"])


# 搜索图片（公开）：按图片名称模糊搜索；关键词为纯数字时，同时按图片ID精确搜索
@reouter.get("/images")
async def search_images(
    request: Request,
    keyword: str = Query(..., min_length=1, description="搜索关键词：模糊匹配图片名称；纯数字时同时匹配图片ID"),
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，1-100"),
    db: AsyncSession = Depends(get_db),
):
    keyword = keyword.strip()
    if not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="搜索关键词不能为空")

    result = await image_crud.search_images_by_keyword(db, keyword, page, page_size)
    result["items"] = [
        image_to_dict(item["image"], request, category_name=item["category_name"])
        for item in result["items"]
    ]
    return success_response('搜索图片成功', data=result)
