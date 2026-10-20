"""统一业务错误。detail 固定为 {code, message, fields?}，前端据此展示。"""
from fastapi import HTTPException, status


def biz_error(code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST,
              fields: dict | None = None) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message, "fields": fields})


# 常用错误
def not_found(message: str = "资源不存在") -> HTTPException:
    return biz_error("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)


def forbidden(message: str = "无权访问该资源") -> HTTPException:
    return biz_error("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


def unauthorized(message: str = "登录已失效，请重新登录") -> HTTPException:
    return biz_error("UNAUTHORIZED", message, status.HTTP_401_UNAUTHORIZED)


def unconfigured(message: str) -> HTTPException:
    """外部服务未配置。"""
    return biz_error("SERVICE_NOT_CONFIGURED", message, status.HTTP_503_SERVICE_UNAVAILABLE)


def service_unavailable(message: str) -> HTTPException:
    return biz_error("SERVICE_UNAVAILABLE", message, status.HTTP_503_SERVICE_UNAVAILABLE)
