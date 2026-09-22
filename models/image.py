from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.category import Category  # noqa: F401  供 ForeignKey 引用，且保证模型被注册

''' 图片表 '''


class Image(Base):
    __tablename__ = "image"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="图片ID")
    title: Mapped[str] = mapped_column(String(100), nullable=False, comment="图片标题")
    url: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="图片地址")
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(Category.id), nullable=False, comment="分类ID"
    )
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="文件大小(字节)")
    # created_at / updated_at 从共享基类 Base 继承，不在此重复定义
