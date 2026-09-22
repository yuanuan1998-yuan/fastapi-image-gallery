"""用户资产：收藏（favorite）与下载记录（download_record）的增删查。

所有函数都在传入的 AsyncSession 上操作，提交由 get_db 依赖统一完成。
"""
from sqlalchemy import select, func, delete

from models.favorite import Favorite
from models.download import DownloadRecord
from models.image import Image
from models.category import Category


# ------------------------------------------------------------ 收藏
async def add_favorite(db, user_id: int, image_id: int) -> bool:
    """收藏某图；已收藏则忽略。返回 True 表示本次新收藏。"""
    exists = await db.scalar(
        select(Favorite.id).where(Favorite.user_id == user_id, Favorite.image_id == image_id)
    )
    if exists:
        return False
    db.add(Favorite(user_id=user_id, image_id=image_id))
    await db.flush()
    return True


async def remove_favorite(db, user_id: int, image_id: int):
    await db.execute(
        delete(Favorite).where(Favorite.user_id == user_id, Favorite.image_id == image_id)
    )


async def is_favorite(db, user_id: int, image_id: int) -> bool:
    return bool(
        await db.scalar(
            select(Favorite.id).where(Favorite.user_id == user_id, Favorite.image_id == image_id)
        )
    )


async def count_favorites(db, user_id: int) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)
        )
        or 0
    )


async def list_favorites(db, user_id: int, page: int, page_size: int):
    total = await count_favorites(db, user_id)
    rows = (
        await db.execute(
            select(Image, Category.name)
            .join(Favorite, Favorite.image_id == Image.id)
            .join(Category, Image.category_id == Category.id, isouter=True)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [{"image": r[0], "category_name": r[1]} for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ------------------------------------------------------------ 下载记录
async def add_download(db, user_id: int, image_id: int):
    rec = DownloadRecord(user_id=user_id, image_id=image_id)
    db.add(rec)
    await db.flush()
    return rec


async def count_downloads(db, user_id: int) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(DownloadRecord).where(DownloadRecord.user_id == user_id)
        )
        or 0
    )


async def list_downloads(db, user_id: int, page: int, page_size: int):
    total = await count_downloads(db, user_id)
    rows = (
        await db.execute(
            select(Image, Category.name)
            .join(DownloadRecord, DownloadRecord.image_id == Image.id)
            .join(Category, Image.category_id == Category.id, isouter=True)
            .where(DownloadRecord.user_id == user_id)
            .order_by(DownloadRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [{"image": r[0], "category_name": r[1]} for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
