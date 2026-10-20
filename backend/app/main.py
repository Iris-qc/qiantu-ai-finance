"""CSAIFM 后端入口：路由挂载、统一错误格式、CORS、OpenAPI 文档（/docs）。"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import ai, analytics, auth, bills, budgets, categories, goals, notifications, profile, reports
from .core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="大学生智能财务管理平台 API（CSAIFM）。金额一律为整数分（元×100）；"
                "所有业务接口需 Bearer Token；未配置的外部 AI 服务会明确返回 503 未配置。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    fields = {}
    for e in exc.errors():
        loc = ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path"))
        fields[loc or "body"] = e.get("msg", "输入不合法")
    return JSONResponse(status_code=422, content={
        "detail": {"code": "VALIDATION_ERROR", "message": "输入校验未通过，请检查表单内容", "fields": fields}
    })


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={
        "detail": {"code": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"}
    })


@app.get("/healthz", tags=["system"])
def healthz():
    return {"status": "ok", "service": settings.app_name}


for r in (auth, profile, categories, bills, budgets, analytics, goals, notifications, reports, ai):
    app.include_router(r.router, prefix=settings.api_prefix)
