import os

import uvicorn
try:
    from dotenv import load_dotenv
    load_dotenv()  # 本地开发时自动读取项目根目录 .env 里的环境变量
except ImportError:
    pass
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import inspect, text

from routers import users, category, image, admin, seach, banner, asset, notice
from config.db_conf import async_engine, AsyncSessionLocal
from models.base import Base
# 建表前必须显式导入所有模型，让表注册到同一个 Base.metadata
import models.users  # noqa: F401
import models.category  # noqa: F401
import models.image  # noqa: F401
import models.admin  # noqa: F401
import models.banner  # noqa: F401
import models.favorite  # noqa: F401
import models.download  # noqa: F401
import models.notice  # noqa: F401

from starlette.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from utils.exception import register_exception_handlers
from utils.cache import cache
from crud.admin import ensure_default_admin

# 上传文件存放目录（项目根目录/uploads），不存在则自动创建
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
# 后台页面所在目录（项目根目录/static）
PAGE_DIR = os.path.join(os.path.dirname(__file__), "static")


def _migrate_columns(conn):
    """给已存在的旧表补充新增列（create_all 不会修改已有表结构）"""
    insp = inspect(conn)
    # news_category 表新增分类封面字段
    if "news_category" in insp.get_table_names():
        columns = {c["name"] for c in insp.get_columns("news_category")}
        if "cover_url" not in columns:
            conn.execute(text(
                "ALTER TABLE news_category ADD COLUMN cover_url VARCHAR(255) "
                "NOT NULL DEFAULT '' COMMENT '分类封面图URL'"
            ))
    # user 表新增微信小程序 openid 列（一键登录用）
    if "user" in insp.get_table_names():
        columns = {c["name"] for c in insp.get_columns("user")}
        if "openid" not in columns:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN openid VARCHAR(64) NULL COMMENT '微信小程序openid'"
            ))
            conn.execute(text(
                "ALTER TABLE user ADD UNIQUE INDEX openid_UNIQUE (openid)"
            ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 启动时自动建表（开发阶段用，生产建议用 Alembic 迁移）
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 2. 旧表结构补齐（新增列）
        await conn.run_sync(_migrate_columns)
    # 3. 确保默认管理员 admin/admin123 与示例数据（轮播海报、公告）存在
    async with AsyncSessionLocal() as session:
        info = await ensure_default_admin(session)
        # 启动日志：明确打印是「新建」还是「已存在跳过」，避免不知道初始账号从哪来
        if info["created"]:
            print(f"[启动] 已初始化管理员账号：{info['username']}（登录后请立即修改密码）")
        else:
            print(f"[启动] 管理员 {info['username']} 已存在，跳过初始化")
        from crud.banner import ensure_default_banners
        await ensure_default_banners(session)
        from crud.notice import ensure_default_notices
        await ensure_default_notices(session)
    # 4. 启动缓存后台清理任务（每 60s 清理一次过期键）
    cache.start_cleanup(interval=60)
    yield
    # 5. 关闭前停止清理任务
    await cache.stop_cleanup()


app = FastAPI(lifespan=lifespan)

# 静态文件服务：uploads/ 目录下的文件通过 /static/文件名 直接访问
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

app.add_middleware(
    # 允许跨域请求
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 部署在 Nginx 之后时，让 request.base_url 拿到正确的公网 scheme/host，
# 这样接口返回的图片完整 URL 才是 https://...（否则会是 http://127.0.0.1:8000）
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.include_router(users.reouter)  # 如果 users.py 里也把 reouter 改成了 router，这里同步改 users.router
app.include_router(category.reouter)
app.include_router(image.reouter)
app.include_router(admin.reouter)
app.include_router(banner.reouter)
app.include_router(seach.reouter)
app.include_router(asset.router)
app.include_router(notice.reouter)
register_exception_handlers(app)   # 加上这一行，全局异常就生效了


# 后台管理页面入口：浏览器访问 http://127.0.0.1:8000/admin
@app.get("/admin")
async def admin_page():
    return FileResponse(os.path.join(PAGE_DIR, "admin.html"))

if __name__ == '__main__':
    uvicorn.run(app="main:app", host="127.0.0.1", port=8000, reload=True)