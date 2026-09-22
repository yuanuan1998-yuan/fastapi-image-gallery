from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

''' 后台管理员表 '''


class Admin(Base):
    __tablename__ = "admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="管理员ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="管理员账号")
    password: Mapped[str] = mapped_column(String(128), nullable=False, comment="密码哈希值")
    # created_at / updated_at 从共享基类 Base 继承
