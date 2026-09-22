from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

''' 分类表 '''


class Category(Base):
    # 图库分类表（created_at / updated_at 从共享基类 Base 继承）
    __tablename__ = 'news_category'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='分类ID')
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment='分类名称')
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='排序顺序')
    cover_url: Mapped[str] = mapped_column(String(255), default="", nullable=False, comment='分类封面图URL')

    def __repr__(self):
        return f'<Category(id = {self.id},name = {self.name},sort_order={self.sort_order})>'



