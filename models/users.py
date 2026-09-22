from typing import Optional

from sqlalchemy import Integer, String, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

''' 用户表 '''


class User(Base):
    """用户信息表ORM模型"""

    __tablename__ = 'user'

    # 创建索引
    __table_args__ = (
        Index('username_UNIQUE', 'username'),
        Index('phone_UNIQUE', 'phone'),
        # 微信小程序 openid（可为 NULL，MySQL 唯一索引允许多个 NULL）
        Index('openid_UNIQUE', 'openid')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String(500), nullable=False, comment="密码(加密存储)")
    nickname: Mapped[Optional[str]] = mapped_column(String(50), comment="昵称")
    avatar: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="头像URL",
        default='https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'   # 截断处补全：vant 默认头像
    )
    gender: Mapped[Optional[str]] = mapped_column(
        Enum('男', '女', '未知'),  # 枚举值必须包含默认值 '未知'，否则 MySQL 报 1265 Data truncated
        comment="性别",
        default='未知'
    )
    bio: Mapped[Optional[str]] = mapped_column(String(500), comment="个人简介", default='这个人很懒，什么都没留下')
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, comment="手机号")
    # 微信小程序身份：wx.login -> code2session 拿到的 openid，同一微信号在同一小程序下固定不变
    openid: Mapped[Optional[str]] = mapped_column(String(64), comment="微信小程序openid")


    def __repr__(self):
        return (f'<User(id ={self.id},username={self.username},'
                f'password={self.password},nickname={self.nickname},'
                f'avatar={self.avatar},gender={self.gender},bio={self.bio}, '
                f'phone={self.phone} )')


# class UserToken(Base):
#     """用户令牌表ORM模型"""
#
#     __tablename__ = 'user_token'
#
#     # 创建索引
#     __table_args__ = (
#         Index('token_UNIQUE', 'token'),
#         Index('fk_user_token_user_idx', 'user_id'),
#     )
#
#     id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="令牌ID")
#     user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False, comment="用户ID")
#     token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="令牌值")
#     expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
#
#     def __repr__(self):
#         return f"<UserToken(id={self.id}, user_id={self.user_id}, token='{self.token}')>"


