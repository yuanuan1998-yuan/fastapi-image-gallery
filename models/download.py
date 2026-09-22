from sqlalchemy import Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.users import User
from models.image import Image


class DownloadRecord(Base):
    """用户下载记录：每次下载都记一条，可分页查看历史"""
    __tablename__ = "download_record"
    __table_args__ = (
        Index("idx_download_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="下载记录ID")
    user_id: Mapped[int] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    image_id: Mapped[int] = mapped_column(
        ForeignKey(Image.id, ondelete="CASCADE"), nullable=False, comment="图片ID"
    )
