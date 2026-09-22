"""
轻量级异步内存 TTL 缓存（无 Redis 依赖，适合个人/小型项目）。

设计原则：
    - DB 是唯一事实来源（SSOT），缓存只是 read-through 加速层
    - 异步环境用 asyncio.Lock 保护并发读写
    - 过期策略：惰性判断 + 后台定时清理，避免无限增长
    - 写操作必须显式失效相关缓存

典型用法：
    # 1) 作为装饰器（自动构造 key：前缀 + 函数参数）
    @cached(ttl=60, prefix="image_list")
    async def get_image_list(category_name: str | None = None, page: int = 1, page_size: int = 10):
        ...

    # 2) 手动读写
    await cache.set("my_key", data, ttl=300)
    data = await cache.get("my_key")
    await cache.invalidate("my_key")
    await cache.invalidate_prefix("image_list")
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger("cache")


class AsyncTTLCache:
    """异步安全的 TTL 内存缓存。"""

    def __init__(self, max_size: int = 2000):
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_at)
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._cleanup_task: asyncio.Task | None = None

    # ---------- 基础读写 ----------

    async def get(self, key: str) -> Any | None:
        """获取缓存，不存在或已过期返回 None。"""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expire_at = entry
            if expire_at and expire_at < time.time():
                self._store.pop(key, None)
                self._misses += 1
                return None
            self._hits += 1
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """写入缓存。ttl 单位秒；None 表示永不过期（直到被显式清理）。"""
        expire_at = (time.time() + ttl) if ttl else None
        async with self._lock:
            # 容量保护：超过 max_size 时清理 20% 过期键
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_locked(ratio=0.2)
            self._store[key] = (value, expire_at)

    # ---------- 失效 ----------

    async def invalidate(self, key: str) -> None:
        """失效单个 key。"""
        async with self._lock:
            self._store.pop(key, None)

    async def invalidate_prefix(self, prefix: str) -> int:
        """失效所有以 prefix 开头的 key，返回清理数量。"""
        async with self._lock:
            keys_to_del = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_del:
                self._store.pop(k, None)
            return len(keys_to_del)

    async def clear(self) -> None:
        """清空全部缓存。"""
        async with self._lock:
            self._store.clear()

    # ---------- 内部 ----------

    def _evict_locked(self, ratio: float = 0.2) -> None:
        """在已持锁状态下清理过期键，若还是超限则按过期时间淘汰最旧的。"""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp is not None and exp < now]
        for k in expired:
            self._store.pop(k, None)
        # 若仍超限，按过期时间升序淘汰
        if len(self._store) >= self._max_size:
            sorted_keys = sorted(
                self._store.keys(),
                key=lambda k: self._store[k][1] or float("inf"),
            )
            to_remove = sorted_keys[: max(1, int(self._max_size * ratio))]
            for k in to_remove:
                self._store.pop(k, None)

    async def _cleanup_loop(self, interval: int = 60) -> None:
        """后台定时清理过期键。"""
        while True:
            try:
                await asyncio.sleep(interval)
                async with self._lock:
                    self._evict_locked(ratio=0.1)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache cleanup error: %s", exc)

    def start_cleanup(self, interval: int = 60) -> None:
        """启动后台清理任务（在 lifespan 中调用一次即可）。"""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_event_loop()
                self._cleanup_task = loop.create_task(self._cleanup_loop(interval))
            except RuntimeError:
                # 还没进入事件循环，稍后由 lifespan 再调
                pass

    async def stop_cleanup(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    # ---------- 指标 ----------

    def stats(self) -> dict[str, int]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total else 0
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 2),
        }


# 全局单例（整个应用共用一个缓存实例）
cache = AsyncTTLCache()


# ============================================================
# 装饰器：让 FastAPI 路由函数一行代码获得缓存能力
# ============================================================

def cached(
    ttl: int = 60,
    prefix: str = "",
    key_builder: Callable[..., str] | None = None,
) -> Callable:
    """
    异步函数缓存装饰器。

    Args:
        ttl: 缓存存活秒数
        prefix: key 前缀（建议每个接口唯一，便于按前缀批量失效）
        key_builder: 自定义 key 构造函数，签名 (**kwargs) -> str；
                     不传则自动用 prefix + 排序后的 kwargs 拼接
    """

    def _auto_key(prefix: str, kwargs: dict[str, Any]) -> str:
        parts = [prefix] if prefix else []
        # 排序保证不同调用顺序得到同一 key
        for k in sorted(kwargs.keys()):
            v = kwargs[k]
            # Request / Response 等对象不参与 key
            if hasattr(v, "base_url") or hasattr(v, "method"):
                continue
            parts.append(f"{k}={v}")
        return ":".join(parts)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 中剔除不参与 key 的参数：
            #   - Request / Response 对象（有 base_url / method 属性）
            #   - DB Session（类名含 "Session"）
            #   - Depends 返回的对象（以 _ 开头的参数，如 _admin）
            def _is_keyable(k: str, v: Any) -> bool:
                if k.startswith("_"):
                    return False
                if hasattr(v, "base_url") or hasattr(v, "method"):
                    return False
                if "Session" in type(v).__name__:
                    return False
                return True

            key_kwargs = {k: v for k, v in kwargs.items() if _is_keyable(k, v)}
            if key_builder is not None:
                key = f"{prefix}:{key_builder(**key_kwargs)}" if prefix else key_builder(**key_kwargs)
            else:
                key = _auto_key(prefix, key_kwargs)

            # 尝试命中缓存
            cached_value = await cache.get(key)
            if cached_value is not None:
                logger.debug("[cache hit] %s", key)
                return cached_value

            # 未命中，执行原函数
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            logger.debug("[cache miss]  %s -> cached %ss", key, ttl)
            return result

        return wrapper

    return decorator
