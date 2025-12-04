# utils/error_handler.py
from fastapi import HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class APIError(Exception):
    """自定義 API 錯誤"""
    def __init__(self, message: str, status_code: int = 500, details: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

def handle_vision_predict_error(error: Exception) -> HTTPException:
    """處理 vision-predict 相關錯誤"""
    logger.error(f"Vision predict error: {error}", exc_info=True)
    return HTTPException(
        status_code=503,
        detail={
            "error": "Vision prediction service unavailable",
            "message": str(error),
            "type": type(error).__name__
        }
    )

async def safe_execute(func, *args, error_handler=None, **kwargs):
    """安全執行函數並處理錯誤"""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if error_handler:
            raise error_handler(e)
        raise HTTPException(status_code=500, detail=str(e))
