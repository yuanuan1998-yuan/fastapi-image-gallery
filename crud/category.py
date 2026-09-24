from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.category import Category
from models.image import Image
from schemas.category import CategoryCreate, CategoryUpdate
from utils.media import to_relative
from config.oss_conf import OSS_ENABLED, OSS_KEY_PREFIX
from utils.s3 import delete_object


# 查询分类列表（附带每个分类下的图片数量）
async def get_create_list(db: AsyncSession):
    categories = (
        await db.execute(select(Category).order_by(Category.sort_order, Category.id))
    ).scalars().all()
    # 一次性统计每个分类的图片数，避免 N+1 查询
    count_rows = (
        await db.execute(
            select(Image.category_id, func.count())
            .group_by(Image.category_id)
        )
    ).all()
    count_map = {cat_id: cnt for cat_id, cnt in count_rows}

    result = []
    for c in categories:
        result.append({
            "id": c.id,
            "name": c.name,
            "sort_order": c.sort_order,
            "cover_url": c.cover_url,
            "image_count": count_map.get(c.id, 0),
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })
    return result


# 新增分类
async def add_category_list(db: AsyncSession, category_data: CategoryCreate):
    # 1. 校验分类名称是否已存在
    exists = (
        await db.execute(select(Category).where(Category.name == category_data.name))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="分类名称已存在"
        )

    # 2. 创建分类
    new_category = Category(
        name=category_data.name,
        sort_order=category_data.sort_order,
        cover_url=to_relative(category_data.cover_url),
    )
    db.add(new_category)
    await db.flush()
    await db.commit()
    await db.refresh(new_category)
    return new_category


# 编辑分类（只更新传入的字段）
async def update_category_list(db: AsyncSession, category_id: int, data: CategoryUpdate):
    category_obj = await db.get(Category, category_id)
    if category_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")

    old_cover = category_obj.cover_url

    # 若要改名，新名称不能与其他分类重复
    if data.name is not None and data.name != category_obj.name:
        dup = (
            await db.execute(select(Category).where(Category.name == data.name))
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="分类名称已存在")
        category_obj.name = data.name
    if data.sort_order is not None:
        category_obj.sort_order = data.sort_order
    if data.cover_url is not None:
        category_obj.cover_url = to_relative(data.cover_url)

    await db.commit()
    await db.refresh(category_obj)

    # 如果更换了封面，删除旧封面文件（OSS 或本地）
    if old_cover and old_cover != category_obj.cover_url:
        if OSS_ENABLED and old_cover.startswith(OSS_KEY_PREFIX):
            try:
                await delete_object(old_cover)
            except Exception as e:
                import logging
                logging.warning(f"删除旧封面 S3 文件失败: key={old_cover}, error={e}")
        else:
            import os
            file_path = os.path.join("uploads", os.path.basename(old_cover))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    import logging
                    logging.warning(f"删除旧封面本地文件失败: path={file_path}, error={e}")

    return category_obj


# 删除分类
async def delete_category_list(db: AsyncSession, category_id: int):
    category_obj = await db.get(Category, category_id)
    if category_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")

    cover_url = category_obj.cover_url

    deleted_category = {
        "id": category_obj.id,
        "name": category_obj.name,
        "sort_order": category_obj.sort_order,
        "cover_url": category_obj.cover_url,
        "created_at": category_obj.created_at,
        "updated_at": category_obj.updated_at,
    }

    try:
        await db.execute(delete(Category).where(Category.id == category_id))
        await db.commit()
    except IntegrityError:
        # 分类下仍有关联图片（外键约束）时，数据库会拒绝删除
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该分类下仍有图片，无法删除",
        )

    # 删除分类后，同步删除封面图片（OSS 或本地）
    if cover_url:
        if OSS_ENABLED and cover_url.startswith(OSS_KEY_PREFIX):
            try:
                await delete_object(cover_url)
            except Exception as e:
                import logging
                logging.warning(f"删除分类封面 S3 文件失败: key={cover_url}, error={e}")
        else:
            import os
            file_path = os.path.join("uploads", os.path.basename(cover_url))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    import logging
                    logging.warning(f"删除分类封面本地文件失败: path={file_path}, error={e}")

    return deleted_category
