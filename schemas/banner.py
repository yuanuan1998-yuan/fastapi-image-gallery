from pydantic import BaseModel, Field


class BannerCreate(BaseModel):
    """新增轮播海报请求体"""
    title: str = Field(default="", max_length=100, description="海报标题/备注")
    image_url: str = Field(min_length=1, max_length=512, description="海报图片地址(相对或外链)")
    link_type: str = Field(default="none", max_length=16, description="跳转类型: none/miniprogram/category/contact")
    link_appid: str = Field(default="", max_length=64, description="目标小程序AppID(miniprogram用)")
    link_path: str = Field(default="", max_length=255, description="目标小程序页面路径(miniprogram用)")
    link_category_id: int = Field(default=0, ge=0, description="跳转到的分类ID(category用)")
    sort_order: int = Field(default=0, ge=0, description="排序，越小越靠前")
    status: int = Field(default=1, ge=0, le=1, description="状态：1启用 0停用")


class BannerUpdate(BaseModel):
    """编辑轮播海报请求体（字段均可选，只更新传入的字段）"""
    title: str | None = Field(default=None, max_length=100, description="海报标题/备注")
    image_url: str | None = Field(default=None, min_length=1, max_length=512, description="海报图片地址")
    link_type: str | None = Field(default=None, max_length=16, description="跳转类型")
    link_appid: str | None = Field(default=None, max_length=64, description="目标小程序AppID")
    link_path: str | None = Field(default=None, max_length=255, description="目标小程序页面路径")
    link_category_id: int | None = Field(default=None, ge=0, description="跳转到的分类ID")
    sort_order: int | None = Field(default=None, ge=0, description="排序")
    status: int | None = Field(default=None, ge=0, le=1, description="状态：1启用 0停用")
