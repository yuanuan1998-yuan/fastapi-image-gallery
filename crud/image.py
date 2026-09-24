import os
import uuid

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.category import Category
from models.image import Image
from utils.media import compress_image
from config.oss_conf import OSS_ENABLED, OSS_KEY_PREFIX
from utils.s3 import upload_object, delete_object

# 上传相关配置（与 main.py 挂载的 /static 静态目录对应）
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
URL_PREFIX = "/static"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MAX_SIZE = 10 * 1024 * 1024  # 上传上限 10MB：前端已压缩，过大直接拒收（方案3 限流防呆）

# 上传到对象存储时设置正确的 Content-Type
_CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}


# 上传图片：按分类名匹配，保存文件并写入数据库
async def upload_image(
    db: AsyncSession,
    category_name: str,
    upload_file: UploadFile,
    title: str | None = None,
):
    # 1. 按分类名称查找分类
    category_obj = (
        await db.execute(select(Category).where(Category.name == category_name.strip()))
    ).scalar_one_or_none()
    if category_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在，请先创建分类"
        )

    # 2. 校验文件扩展名与类型
    _, ext = os.path.splitext(upload_file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式，仅支持：{', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if not (upload_file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="上传的文件不是图片类型"
        )

    # 3. 读取内容并校验大小
    content = await upload_file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传的文件为空")
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片过大（上限 10MB），请先在本地压缩后上传",
        )

    # 4. 压缩图片（智能决策：小图/动图/透明图原样，大图等比缩放到 1920px + JPEG quality=80）
    compressed_bytes, new_ext, new_size = compress_image(content, original_ext=ext)

    # 5. 生成唯一文件名；OSS 开启时上传到对象存储，否则存本地 uploads 目录
    stored_name = f"{uuid.uuid4().hex}.{new_ext}"
    content_type = _CONTENT_TYPES.get(new_ext, "application/octet-stream")
    if OSS_ENABLED:
        from config.oss_conf import require_oss_conf
        require_oss_conf()
        # 普通图片放到 images/photos/ 子目录，和 banners/covers 分开
        key = f"{OSS_KEY_PREFIX}photos/{stored_name}"
        await upload_object(key, compressed_bytes, content_type)
        image_url = key
    else:
        photos_dir = os.path.join(UPLOAD_DIR, "photos")
        os.makedirs(photos_dir, exist_ok=True)
        save_path = os.path.join(photos_dir, stored_name)
        with open(save_path, "wb") as f:
            f.write(compressed_bytes)
        image_url = f"{URL_PREFIX}/photos/{stored_name}"

    # 6. 写入数据库（url 只存对象 key 或相对路径；完整域名在响应时拼接）
    image_title = title.strip() if title and title.strip() else os.path.splitext(upload_file.filename)[0]
    image = Image(
        title=image_title,
        url=image_url,
        category_id=category_obj.id,
        file_size=new_size,
    )
    db.add(image)
    await db.flush()
    await db.commit()
    await db.refresh(image)
    return image


# 图片列表（可按分类名筛选 + 分页，按 id 倒序）
async def get_image_list(
    db: AsyncSession,
    category_name: str | None = None,
    page: int = 1,
    page_size: int = 10,
):
    stmt = select(Image, Category.name).join(Category, Image.category_id == Category.id)
    count_stmt = select(func.count()).select_from(Image)

    if category_name:
        category_obj = (
            await db.execute(select(Category).where(Category.name == category_name.strip()))
        ).scalar_one_or_none()
        if category_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
        stmt = stmt.where(Image.category_id == category_obj.id)
        count_stmt = count_stmt.where(Image.category_id == category_obj.id)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(Image.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()
    items = [{"image": row[0], "category_name": row[1]} for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# 搜索图片：可按图片ID精确查找，或用关键词同时模糊匹配图片标题与分类名称
async def search_images(
    db: AsyncSession,
    keyword: str | None = None,
    image_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
):
    # join 分类表，这样关键词可以同时匹配分类名；查出的分类名一并返回给前端
    stmt = (
        select(Image, Category.name)
        .join(Category, Image.category_id == Category.id)
    )
    count_stmt = (
        select(func.count())
        .select_from(Image)
        .join(Category, Image.category_id == Category.id)
    )

    conditions = []
    # 按图片ID精确匹配
    if image_id is not None:
        conditions.append(Image.id == image_id)
    # 关键词：模糊匹配图片标题 或 分类名称（任一命中即可）
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        conditions.append(or_(Image.title.like(kw), Category.name.like(kw)))

    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(Image.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()
    # 每行是 (Image对象, 分类名)
    items = [{"image": row[0], "category_name": row[1]} for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# 专用搜索：按图片名称模糊匹配；关键词为纯数字时，同时按图片ID精确匹配
async def search_images_by_keyword(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    page_size: int = 10,
):
    kw = keyword.strip()
    stmt = (
        select(Image, Category.name)
        .join(Category, Image.category_id == Category.id)
    )
    count_stmt = (
        select(func.count())
        .select_from(Image)
        .join(Category, Image.category_id == Category.id)
    )

    # 图片名称模糊匹配
    condition = Image.title.like(f"%{kw}%")
    # 纯数字关键词：ID 精确匹配 或 名称模糊匹配，任一命中即可
    if kw.isdigit():
        condition = or_(Image.id == int(kw), condition)

    stmt = stmt.where(condition)
    count_stmt = count_stmt.where(condition)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(Image.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()
    items = [{"image": row[0], "category_name": row[1]} for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# 批量上传：多张图片归入同一分类，单张失败不影响其他图片，返回成功/失败明细
async def batch_upload_images(
    db: AsyncSession,
    category_name: str,
    files: list[UploadFile],
):
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择要上传的图片")

    success, failed = [], []
    for f in files:
        try:
            image = await upload_image(db, category_name, f)
            success.append({"id": image.id, "title": image.title, "url": image.url,
                            "category_id": image.category_id, "file_size": image.file_size})
        except HTTPException as e:
            # 单张失败（格式/大小等）记录原因，继续处理后续图片
            failed.append({"filename": f.filename, "reason": e.detail})
    return {"total": len(files), "success_count": len(success),
            "failed_count": len(failed), "success": success, "failed": failed}


# 编辑图片：可改标题、可按分类名调整所属分类
async def update_image(
    db: AsyncSession,
    image_id: int,
    title: str | None = None,
    category_name: str | None = None,
):
    image = (
        await db.execute(select(Image).where(Image.id == image_id))
    ).scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

    if title is not None:
        title = title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片标题不能为空")
        image.title = title

    if category_name is not None:
        category_name = category_name.strip()
        category_obj = (
            await db.execute(select(Category).where(Category.name == category_name))
        ).scalar_one_or_none()
        if category_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在，请先创建分类")
        image.category_id = category_obj.id

    await db.commit()
    await db.refresh(image)
    return image


# 图片详情（join 分类表，附带分类名称与分类封面）
async def get_image(db: AsyncSession, image_id: int):
    row = (
        await db.execute(
            select(Image, Category.name, Category.cover_url)
            .join(Category, Image.category_id == Category.id)
            .where(Image.id == image_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    return {"image": row[0], "category_name": row[1], "category_cover": row[2]}


# 删除图片（OSS 开启走对象存储删除，否则删本地文件）
async def delete_image(db: AsyncSession, image_id: int):
    image = (
        await db.execute(select(Image).where(Image.id == image_id))
    ).scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

    deleted_image = {
        "id": image.id,
        "title": image.title,
        "url": image.url,
        "category_id": image.category_id,
        "file_size": image.file_size,
        "created_at": image.created_at,
        "updated_at": image.updated_at,
    }

    # 先删实际文件（OSS 或本地），再删数据库记录
    # 兼容两种格式：相对 key（images/xxx.jpg）或完整公网 URL（https://xxx.s3.bitiful.net/images/xxx.jpg）
    file_deleted = False
    if OSS_ENABLED:
        from config.oss_conf import OSS_BUCKET
        s3_key = None
        if image.url.startswith(OSS_KEY_PREFIX):
            s3_key = image.url
        elif f"{OSS_BUCKET}.s3.bitiful.net" in image.url:
            parts = image.url.split(f"{OSS_BUCKET}.s3.bitiful.net/")
            if len(parts) > 1:
                s3_key = parts[1].split("?")[0]

        if s3_key:
            try:
                await delete_object(s3_key)
                file_deleted = True
            except Exception as e:
                import logging
                logging.warning(f"删除 S3 文件失败: key={s3_key}, error={e}")

    if not file_deleted:
        file_path = os.path.join(UPLOAD_DIR, os.path.basename(image.url))
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                import logging
                logging.warning(f"删除本地文件失败: path={file_path}, error={e}")

    await db.execute(delete(Image).where(Image.id == image_id))
    await db.commit()

    return deleted_image


# 批量删除图片（同步删除 S3 文件）
async def batch_delete_images(db: AsyncSession, image_ids: list[int]):
    if not image_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择要删除的图片")

    images = (
        await db.execute(select(Image).where(Image.id.in_(image_ids)))
    ).scalars().all()

    if not images:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

    from config.oss_conf import OSS_BUCKET
    deleted_ids = []
    failed = []

    for img in images:
        try:
            file_deleted = False
            if OSS_ENABLED:
                s3_key = None
                if img.url.startswith(OSS_KEY_PREFIX):
                    s3_key = img.url
                elif f"{OSS_BUCKET}.s3.bitiful.net" in img.url:
                    parts = img.url.split(f"{OSS_BUCKET}.s3.bitiful.net/")
                    if len(parts) > 1:
                        s3_key = parts[1].split("?")[0]

                if s3_key:
                    try:
                        await delete_object(s3_key)
                        file_deleted = True
                    except Exception as e:
                        import logging
                        logging.warning(f"批量删除 S3 失败: key={s3_key}, error={e}")

            if not file_deleted:
                file_path = os.path.join(UPLOAD_DIR, os.path.basename(img.url))
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass

            deleted_ids.append(img.id)
        except Exception as e:
            failed.append({"id": img.id, "title": img.title, "reason": str(e)})

    if deleted_ids:
        await db.execute(delete(Image).where(Image.id.in_(deleted_ids)))
        await db.commit()

    return {
        "success_count": len(deleted_ids),
        "failed_count": len(failed),
        "deleted_ids": deleted_ids,
        "failed": failed,
    }
