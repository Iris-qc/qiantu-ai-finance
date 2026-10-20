"""外部 AI 服务适配层（OpenAI 兼容 HTTP 接口）。所有密钥来自环境变量，代码不携带任何密钥。"""
from . import llm, mail, ocr, speech

__all__ = ["llm", "speech", "ocr", "mail"]
