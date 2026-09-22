from pydantic import BaseModel, Field, field_validator


class AdminLogin(BaseModel):
    """管理员登录"""
    username: str = Field(min_length=1, max_length=50, description="管理员账号")
    password: str = Field(min_length=1, max_length=64, description="密码")

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        return v.strip()


class AdminCreate(BaseModel):
    """新增管理员"""
    username: str = Field(min_length=2, max_length=50, description="管理员账号")
    password: str = Field(min_length=6, max_length=64, description="密码，至少6位")

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("账号不能为空白字符")
        return v


class PasswordChange(BaseModel):
    """修改密码"""
    old_password: str = Field(min_length=1, max_length=64, description="原密码")
    new_password: str = Field(min_length=6, max_length=64, description="新密码，至少6位")
