import asyncio
import os
import random
import uuid

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select, func

from config.db_conf import async_engine, AsyncSessionLocal
from models.base import Base
import models.category  # noqa: F401  注册表映射
import models.image  # noqa: F401

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 尝试加载系统中的中文字体，否则用默认字体
FONT = None
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
          r"C:\Windows\Fonts\simsun.ttc"):
    if os.path.exists(fp):
        try:
            FONT = ImageFont.truetype(fp, 64)
            break
        except Exception:
            pass

# 宠物分类：名称 + 渐变两色（顶/底）
CATEGORIES = [
    ("柯基",       (255, 159, 64),  (255, 214, 140)),
    ("萨摩耶",     (120, 200, 255), (205, 238, 255)),
    ("比熊",       (205, 232, 255), (255, 255, 255)),
    ("泰迪",       (214, 144, 92),  (246, 212, 172)),
    ("金毛",       (255, 196, 0),   (255, 236, 132)),
    ("哈士奇",     (92, 122, 162),  (182, 207, 232)),
    ("布偶猫",     (240, 182, 202), (255, 226, 236)),
    ("英国短毛猫", (150, 150, 162), (212, 212, 222)),
]

PER_CAT = 4  # 每个分类 4 张 → 8×4=32 张，约 3 页（每页 10 张）


def make_image(name, idx, c1, c2):
    w = 800
    h = random.randint(660, 1080)  # 不同高度，瀑布流更自然
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        col = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=col)

    text = f"{name} · {idx}"
    if FONT:
        bbox = draw.textbbox((0, 0), text, font=FONT)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w - tw) / 2, (h - th) / 2), text, fill=(40, 40, 40), font=FONT)
    else:
        draw.text((w // 2 - 120, h // 2), text, fill=(40, 40, 40))

    fn = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(UPLOAD_DIR, fn)
    img.save(path, "JPEG", quality=85)
    return f"/static/{fn}", os.path.getsize(path)


async def seed():
    # 确保表存在（空白库也能跑）
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # 已有的分类名 → 对象
        existing = {
            c.name: c
            for c in (await session.scalars(select(models.category.Category))).all()
        }

        added_cats = 0
        added_imgs = 0
        sort_start = (max((c.sort_order for c in existing.values()), default=0)) + 1

        for i, (name, c1, c2) in enumerate(CATEGORIES):
            cat = existing.get(name)
            if cat is None:
                cat = models.category.Category(
                    name=name, sort_order=sort_start + i, cover_url=""
                )
                session.add(cat)
                await session.flush()
                added_cats += 1

            # 该分类已有图片数，不足则补足到 PER_CAT
            cnt = await session.scalar(
                select(func.count())
                .select_from(models.image.Image)
                .where(models.image.Image.category_id == cat.id)
            )
            need = PER_CAT - cnt
            for k in range(need):
                url, size = make_image(name, cnt + k + 1, c1, c2)
                session.add(models.image.Image(
                    title=f"{name} 萌照 {cnt + k + 1}",
                    url=url,
                    category_id=cat.id,
                    file_size=size,
                ))
                added_imgs += 1
                if k == 0 and not cat.cover_url:
                    cat.cover_url = url

        await session.commit()
        print(f"ADDED categories={added_cats}, images={added_imgs}.")


if __name__ == "__main__":
    asyncio.run(seed())
    asyncio.run(async_engine.dispose())
