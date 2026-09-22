from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

''' 小程序公告表 '''


class Notice(Base):
    """公告：首页公告栏上下轮播标题 → 公告列表 → 公告详情（正文）。

    status：1 启用（小程序可见） 0 停用（仅后台可见）
    sort_order：越小越靠前
    created_at / updated_at 从共享基类 Base 继承
    """

    __tablename__ = 'notice'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='公告ID')
    title: Mapped[str] = mapped_column(String(200), default='', nullable=False, comment='公告标题')
    content: Mapped[str] = mapped_column(Text, default='', nullable=False, comment='公告正文')
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='排序，越小越靠前')
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment='状态：1启用 0停用')

    def __repr__(self):
        return f'<Notice(id={self.id}, title={self.title}, status={self.status})>'
