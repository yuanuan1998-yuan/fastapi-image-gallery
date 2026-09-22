from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.notice import Notice


def _summary(n: Notice) -> dict:
    """列表 / 首页轮播用：不带正文，减小响应体积"""
    return {
        "id": n.id,
        "title": n.title,
        "sort_order": n.sort_order,
        "status": n.status,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
    }


def _detail(n: Notice) -> dict:
    data = _summary(n)
    data["content"] = n.content
    return data


# 公开列表：只返回启用中的公告，按排序 + id 升序（首页公告栏与公告列表页共用同一个接口）
async def get_enabled_list(db: AsyncSession):
    rows = (
        await db.execute(
            select(Notice).where(Notice.status == 1).order_by(Notice.sort_order, Notice.id)
        )
    ).scalars().all()
    return [_summary(n) for n in rows]


# 公开详情：停用/不存在的公告一律当作不存在
async def get_enabled_detail(db: AsyncSession, notice_id: int):
    n = await db.get(Notice, notice_id)
    if n is None or n.status != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在或已下架")
    return _detail(n)


# 管理列表：含停用，供后台编辑
async def get_all(db: AsyncSession):
    rows = (
        await db.execute(select(Notice).order_by(Notice.sort_order, Notice.id))
    ).scalars().all()
    return [_detail(n) for n in rows]


async def create_notice(db: AsyncSession, data) -> dict:
    n = Notice(
        title=data.title,
        content=data.content,
        sort_order=data.sort_order,
        status=data.status,
    )
    db.add(n)
    await db.flush()
    await db.commit()
    await db.refresh(n)
    return _detail(n)


async def update_notice(db: AsyncSession, notice_id: int, data) -> dict:
    n = await db.get(Notice, notice_id)
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")

    if data.title is not None:
        n.title = data.title
    if data.content is not None:
        n.content = data.content
    if data.sort_order is not None:
        n.sort_order = data.sort_order
    if data.status is not None:
        n.status = data.status

    await db.commit()
    await db.refresh(n)
    return _detail(n)


async def delete_notice(db: AsyncSession, notice_id: int) -> dict:
    n = await db.get(Notice, notice_id)
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    info = _detail(n)
    await db.execute(delete(Notice).where(Notice.id == notice_id))
    await db.commit()
    return info


# 首次启动且表为空时填充 3 条示例公告，方便直接联调
async def ensure_default_notices(db: AsyncSession):
    exists = (await db.execute(select(Notice))).scalars().first()
    if exists is not None:
        return
    samples = [
        Notice(
            title="咸虾米壁纸，版权公告",
            content=(
                "本站所有图片均来源于网络，仅供个人学习与欣赏使用。\n\n"
                "如有侵权，请联系客服，我们会在收到通知后第一时间删除。"
            ),
            sort_order=1, status=1,
        ),
        Notice(
            title="关于近期部分图片加载缓慢的说明",
            content=(
                "近期服务器在升级带宽，部分大图首屏加载可能稍慢，稍后会恢复正常。\n\n"
                "感谢理解与支持。"
            ),
            sort_order=2, status=1,
        ),
        Notice(
            title="新版公告功能已上线",
            content=(
                "首页新增公告栏，可上下轮播多条公告。\n"
                "点击公告栏可查看全部公告，点进单条即可查看详情。"
            ),
            sort_order=3, status=1,
        ),
    ]
    db.add_all(samples)
    await db.commit()
