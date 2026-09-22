"""全局异常处理

统一错误响应格式（与 utils/response.py 的 success_response 保持一致）：
{
    "code": 400,
    "message": "面向用户的中文提示",
    "data": None
}

使用方式：在 main.py 中调用 register_exception_handlers(app)
"""

import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


class BusinessException(Exception):
    """业务异常：在业务代码中主动抛出，例如 raise BusinessException(400, '该用户已存在')"""

    def __init__(self, code: int = 400, message: str = '业务处理失败'):
        self.code = code
        self.message = message
        super().__init__(message)


def _error_response(code: int, message: str, status_code: int | None = None,
                    data: dict | None = None) -> JSONResponse:
    """构造统一错误响应；HTTP 状态码默认与业务 code 保持一致"""
    return JSONResponse(
        status_code=status_code if status_code is not None else code,
        content={
            'code': code,
            'message': message,
            'data': data,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全部全局异常处理器"""

    # 1. 业务异常：直接返回自定义的中文提示
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return _error_response(exc.code, exc.message)

    # 2. HTTP 异常（含手动 raise HTTPException）：保留状态码，detail 作为提示
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else '请求错误'
        return _error_response(exc.status_code, message)

    # 3. 参数校验异常（FastAPI 自动返回 422）：把字段错误转成中文提示
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 取第一条错误，形如：("query", "category_id") -> category_id
        first_error = exc.errors()[0] if exc.errors() else {}
        location = first_error.get('loc') or ()
        field = location[-1] if location else ''
        err_type = first_error.get('type', '')

        if err_type == 'missing':
            message = f'缺少必填参数: {field}' if field else '缺少必填参数'
        elif err_type in ('value_error', 'type_error'):
            message = f'参数 {field} 格式不正确' if field else '参数格式不正确'
        else:
            message = f'参数 {field} 校验失败' if field else '参数校验失败'

        return _error_response(422, message)

    # 4. 兜底异常：未被前面捕获的所有异常，避免堆栈直接以非 JSON 形式泄露
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        trace_id = uuid.uuid4().hex
        tb_str = traceback.format_exc()
        # 堆栈同时打到服务端日志，便于在终端定位
        traceback.print_exc()

        # 数据库类异常给更友好的提示，其它异常给通用提示
        if isinstance(exc, SQLAlchemyError):
            message = '数据库操作失败，请稍后重试'
        else:
            message = f'服务器内部错误，错误编号: {trace_id}'

        return _error_response(
            code=500,
            message=message,
            data={
                'error_type': type(exc).__name__,   # 异常类名，如 ArgumentError
                'error_detail': str(exc),           # 异常具体信息
                'traceback': tb_str,                # 完整堆栈字符串
            },
        )
