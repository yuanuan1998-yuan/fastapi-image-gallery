from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import os
import logging

from models.banner import Banner
from utils.media import to_relative
from config.oss_conf import OSS_ENABLED, OSS_KEY_PREFIX
from utils.s3 import delete_object


def _to_dict(b: Banner) -> dict:
    return {
        "id": b.id,
        "title": b.title,
        "image_url": b.image_url,
        "link_type": b.link_type,
        "link_appid": b.link_appid,
        "link_path": b.link_path,
        "link_category_id": b.link_category_id,
        "sort_order": b.sort_order,
        "status": b.status,
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


# 公开列表：只返回启用中的海报，按排序 + id 升序
async def get_enabled_list(db: AsyncSession):
    rows = (
        await db.execute(
            select(Banner).where(Banner.status == 1).order_by(Banner.sort_order, Banner.id)
        )
    ).scalars().all()
    return [_to_dict(b) for b in rows]


# 管理列表：返回全部（含停用），供后台编辑
async def get_all(db: AsyncSession):
    rows = (
        await db.execute(select(Banner).order_by(Banner.sort_order, Banner.id))
    ).scalars().all()
    return [_to_dict(b) for b in rows]


async def create_banner(db: AsyncSession, data) -> dict:
    b = Banner(
        title=data.title,
        image_url=to_relative(data.image_url),
        link_type=data.link_type,
        link_appid=data.link_appid,
        link_path=data.link_path,
        link_category_id=data.link_category_id,
        sort_order=data.sort_order,
        status=data.status,
    )
    db.add(b)
    await db.flush()
    await db.commit()
    await db.refresh(b)
    return _to_dict(b)


async def update_banner(db: AsyncSession, banner_id: int, data) -> dict:
    b = await db.get(Banner, banner_id)
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="海报不存在")

    old_image_url = b.image_url

    if data.title is not None:
        b.title = data.title
    if data.image_url is not None:
        b.image_url = to_relative(data.image_url)
    if data.link_type is not None:
        b.link_type = data.link_type
    if data.link_appid is not None:
        b.link_appid = data.link_appid
    if data.link_path is not None:
        b.link_path = data.link_path
    if data.link_category_id is not None:
        b.link_category_id = data.link_category_id
    if data.sort_order is not None:
        b.sort_order = data.sort_order
    if data.status is not None:
        b.status = data.status

    await db.commit()
    await db.refresh(b)

    # 如果更换了图片，删除旧图片文件
    if old_image_url and old_image_url != b.image_url:
        # 跳过外链图片（http 开头）
        if not old_image_url.startswith("http"):
            if OSS_ENABLED and old_image_url.startswith(OSS_KEY_PREFIX):
                try:
                    await delete_object(old_image_url)
                except Exception as e:
                    logging.warning(f"删除轮播海报旧图 S3 失败: key={old_image_url}, error={e}")
            else:
                file_path = os.path.join("uploads", os.path.basename(old_image_url))
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        logging.warning(f"删除轮播海报旧图本地失败: path={file_path}, error={e}")

    return _to_dict(b)


async def delete_banner(db: AsyncSession, banner_id: int) -> dict:
    b = await db.get(Banner, banner_id)
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="海报不存在")
    info = _to_dict(b)

    # 先删实际文件，再删数据库记录
    image_url = b.image_url
    if image_url and not image_url.startswith("http"):
        if OSS_ENABLED and image_url.startswith(OSS_KEY_PREFIX):
            try:
                await delete_object(image_url)
            except Exception as e:
                logging.warning(f"删除轮播海报 S3 失败: key={image_url}, error={e}")
        else:
            file_path = os.path.join("uploads", os.path.basename(image_url))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    logging.warning(f"删除轮播海报本地失败: path={file_path}, error={e}")

    await db.execute(delete(Banner).where(Banner.id == banner_id))
    await db.commit()
    return info


# 首次启动且表为空时，填充 3 条示例海报，覆盖三种跳转类型，方便直接联调
async def ensure_default_banners(db: AsyncSession):
    count = (await db.execute(select(Banner))).scalars().first()
    if count is not None:
        return
    samples = [
        Banner(
            title="示例·跳转分类",
            image_url="https://picsum.photos/seed/banner_cat/750/300",
            link_type="category", link_category_id=1, sort_order=1, status=1,
        ),
        Banner(
            title="示例·联系客服",
            image_url="https://picsum.photos/seed/banner_kf/750/300",
            link_type="contact", sort_order=2, status=1,
        ),
        Banner(
            title="示例·跳转别的小程序",
            image_url="https://picsum.photos/seed/banner_mp/750/300",
            link_type="miniprogram",
            link_appid="wx1234567890abcdef", link_path="pages/index/index",
            sort_order=3, status=1,
        ),
    ]
    db.add_all(samples)
    await db.commit()
