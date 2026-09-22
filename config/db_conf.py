import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 本地默认连本机 MySQL；部署到 PythonAnywhere 时通过环境变量 DATABASE_URL 覆盖
# PythonAnywhere 免费版用 SQLite，生产/本地用 MySQL
ASYNC_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./mysite.db",
)

# 根据数据库类型选择连接池参数
_is_sqlite = ASYNC_DATABASE_URL.startswith("sqlite")
_engine_kwargs = {"echo": False}
if not _is_sqlite:
    _engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    })

async_engine = create_async_engine(ASYNC_DATABASE_URL, **_engine_kwargs)


# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, # 绑定数据库引擎
    class_=AsyncSession, # 指定会话类
    expire_on_commit=False # 会话对象不过期，不重新查询数据库
)
# 依赖项，用于获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session # 返回数据库会话给路由处理函数
            await session.commit() # 无异常，提交事务
        except Exception:
            await session.rollback() # 有异常则回滚
            raise
        finally:
            await session.close() # 关闭会话













