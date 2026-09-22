from sqlalchemy import Integer, String

from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

''' 首页轮播海报表 '''


class Banner(Base):
    """
    首页轮播海报：管理员可自定义图片与跳转行为。
    link_type 取值：
        none         = 仅展示，不跳转
        miniprogram  = 跳转到别的小程序（需 link_appid + link_path）
        category     = 跳转到指定分类（需 link_category_id）
        contact      = 直接打开微信客服会话
    """

    __tablename__ = "banner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="海报ID")
    title: Mapped[str] = mapped_column(String(100), default="", nullable=False, comment="海报标题/备注")
    image_url: Mapped[str] = mapped_column(String(512), nullable=False, default="", comment="海报图片地址(相对或外链)")
    # 跳转类型
    link_type: Mapped[str] = mapped_column(String(16), default="none", nullable=False, comment="跳转类型 none/miniprogram/category/contact")
    # 跳转别的小程序用
    link_appid: Mapped[str] = mapped_column(String(64), default="", nullable=False, comment="目标小程序AppID")
    link_path: Mapped[str] = mapped_column(String(255), default="", nullable=False, comment="目标小程序页面路径")
    # 跳转分类用
    link_category_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="跳转到的分类ID")
    # 排序与状态
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序，越小越靠前")
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="状态：1启用 0停用")
