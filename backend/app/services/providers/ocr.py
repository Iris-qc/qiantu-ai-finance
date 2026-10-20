"""图片 OCR 适配（OpenAI 兼容多模态 /chat/completions，图片以 data URL 传入）。未配置时由上层返回"未配置"。"""
import base64

import httpx

_PROMPT = """你是票据识别助手。识别这张购物小票/订单截图/电子账单图片中的文字，原样输出所有可见文字（每行一条），不要解释。"""


def ocr_image(base_url: str, api_key: str, model: str, image_bytes: bytes,
              mime: str = "image/jpeg", timeout: float = 30.0) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    data_url = f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii")
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "请识别图片中的全部文字"},
                ]},
            ],
            "temperature": 0,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
