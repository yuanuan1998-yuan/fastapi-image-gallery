from pydantic import BaseModel, Field, field_validator


class CategoryCreate(BaseModel):
    """新增分类请求体"""
    name: str = Field(min_length=1, max_length=50, description="分类名称")
    sort_order: int = Field(default=0, ge=0, description="排序顺序，数字越小越靠前")
    cover_url: str = Field(default="", max_length=255, description="分类封面图URL")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("分类名称不能为空白字符")
        return v


class CategoryUpdate(BaseModel):
    """编辑分类请求体（字段均可选，只更新传入的字段）"""
    name: str | None = Field(default=None, min_length=1, max_length=50, description="分类名称")
    sort_order: int | None = Field(default=None, ge=0, description="排序顺序")
    cover_url: str | None = Field(default=None, max_length=255, description="分类封面图URL")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("分类名称不能为空白字符")
        return v
