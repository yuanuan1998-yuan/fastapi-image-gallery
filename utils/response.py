from fastapi.encoders import jsonable_encoder

from starlette.responses import JSONResponse


def success_response(message: str ='success' , data= None):
    content = {
        'code': 200,
        'message': message,
        'data': data
    }

    # 目标:把任何的FastAPI、Pydantic、0RM 对象都要正常响应 -> code、message、data
    return JSONResponse(content=jsonable_encoder(content), status_code=200)
