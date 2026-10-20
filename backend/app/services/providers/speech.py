"""语音转写适配（OpenAI 兼容 /audio/transcriptions）。未配置时由上层返回"未配置"。"""
import httpx


def transcribe(base_url: str, api_key: str, model: str, audio_bytes: bytes,
               filename: str = "audio.webm", timeout: float = 30.0) -> str:
    url = base_url.rstrip("/") + "/audio/transcriptions"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        data={"model": model},
        files={"file": (filename, audio_bytes, "application/octet-stream")},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["text"]
