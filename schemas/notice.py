from pydantic import BaseModel, Field


class NoticeCreate(BaseModel):
    """新增公告请求体"""
    title: str = Field(min_length=1, max_length=200, description="公告标题")
    content: str = Field(default="", description="公告正文")
    sort_order: int = Field(default=0, ge=0, description="排序，越小越靠前")
    status: int = Field(default=1, ge=0, le=1, description="状态：1启用 0停用")


class NoticeUpdate(BaseModel):
    """编辑公告请求体（字段均可选，只更新传入的字段）"""
    title: str | None = Field(default=None, min_length=1, max_length=200, description="公告标题")
    content: str | None = Field(default=None, description="公告正文")
    sort_order: int | None = Field(default=None, ge=0, description="排序")
    status: int | None = Field(default=None, ge=0, le=1, description="状态：1启用 0停用")
