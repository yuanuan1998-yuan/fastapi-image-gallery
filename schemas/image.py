from pydantic import BaseModel, Field, field_validator


class ImageUpdate(BaseModel):
    """编辑图片请求体（字段均可选，只更新传入的字段）"""
    title: str | None = Field(default=None, min_length=1, max_length=100, description="新的图片标题")
    category_name: str | None = Field(default=None, min_length=1, max_length=50, description="目标分类名称")

    @field_validator("title", "category_name")
    @classmethod
    def strip_value(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("不能为空白字符")
        return v
