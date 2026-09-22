from sqlalchemy import Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.users import User
from models.image import Image


class Favorite(Base):
    """用户收藏：一个用户对同一张图只收藏一次（user_id + image_id 唯一）"""
    __tablename__ = "favorite"
    __table_args__ = (
        Index("uq_favorite_user_image", "user_id", "image_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="收藏ID")
    user_id: Mapped[int] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    image_id: Mapped[int] = mapped_column(
        ForeignKey(Image.id, ondelete="CASCADE"), nullable=False, comment="图片ID"
    )
