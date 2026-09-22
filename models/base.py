from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """全项目唯一的 ORM 基类，所有模型都必须继承它，
    这样 main.py 的 Base.metadata.create_all 才能一次性创建全部表。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, insert_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, insert_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
