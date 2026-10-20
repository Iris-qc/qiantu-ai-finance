"""LLM 对话适配（OpenAI 兼容 /chat/completions）。"""
import json

import httpx


def chat_json(base_url: str, api_key: str, model: str, *, system: str, user: str,
              timeout: float = 20.0) -> str:
    """请求返回 JSON 文本（要求模型输出纯 JSON）。"""
    url = base_url.rstrip("/") + "/chat/completions"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def chat(base_url: str, api_key: str, model: str, *, system: str, user: str,
         timeout: float = 20.0) -> str:
    """普通对话，返回文本。"""
    return chat_json(base_url, api_key, model, system=system, user=user, timeout=timeout)


def json_reply(base_url: str, api_key: str, model: str, *, system: str, user: str,
               timeout: float = 20.0) -> dict:
    """要求返回 JSON 对象。"""
    raw = chat_json(base_url, api_key, model, system=system + " 只输出 JSON。", user=user, timeout=timeout)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
