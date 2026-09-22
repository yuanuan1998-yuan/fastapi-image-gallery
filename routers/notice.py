"""公告接口。

前缀 /api/notice：
  GET    /list              公开：启用中的公告列表（首页公告栏 + 公告列表页共用，不含正文）
  GET    /{notice_id}       公开：公告详情（含正文 content）
  GET    /admin/list        管理：全部公告（含停用）
  POST   /add               管理：新增公告
  PUT    /update/{id}       管理：编辑公告
  DELETE /{notice_id}       管理：删除公告

注意：/list、/admin/list 必须注册在 /{notice_id} 之前，避免路径被当成 notice_id。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from utils.response import success_response
from utils.admin_auth import get_current_admin
from utils.cache import cached, cache
from crud import notice as notice_crud
from schemas.notice import NoticeCreate, NoticeUpdate
from config.db_conf import get_db

reouter = APIRouter(prefix="/api/notice", tags=["notice"])


# ------------------------------------------------------------ 公开接口
@reouter.get("/list")
@cached(ttl=300, prefix="notice_list")
async def list_notices(request: Request, db: AsyncSession = Depends(get_db)):
    data = await notice_crud.get_enabled_list(db)
    return success_response('获取公告列表成功', data=data)


# ------------------------------------------------------------ 管理接口
@reouter.get("/admin/list")
async def admin_list_notices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return success_response('获取公告列表成功', data=await notice_crud.get_all(db))


@reouter.post("/add")
async def add_notice(
    data: NoticeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    n = await notice_crud.create_notice(db, data)
    await cache.invalidate_prefix("notice_list")
    return success_response('添加公告成功', data=n)


@reouter.put("/update/{notice_id}")
async def update_notice(
    notice_id: int,
    data: NoticeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    n = await notice_crud.update_notice(db, notice_id, data)
    await cache.invalidate_prefix("notice_list")
    return success_response('更新公告成功', data=n)


@reouter.delete("/{notice_id}")
async def delete_notice(
    notice_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    info = await notice_crud.delete_notice(db, notice_id)
    await cache.invalidate_prefix("notice_list")
    return success_response('删除公告成功', data=info)


@reouter.get("/{notice_id}")
async def get_notice(
    notice_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await notice_crud.get_enabled_detail(db, notice_id)
    return success_response('获取公告详情成功', data=data)
