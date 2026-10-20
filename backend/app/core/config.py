"""应用配置：全部通过环境变量 / .env 覆盖，不含任何密钥默认值（仅本地开发默认）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "大学生智能财务管理平台 CSAIFM"
    api_prefix: str = "/api"
    # 业务时区：所有"月/日"边界按此时区计算；数据库存 UTC。
    app_tz: str = "Asia/Shanghai"

    database_url: str = "postgresql+psycopg://csaifm:csaifm@localhost:5433/csaifm"

    jwt_secret: str = "dev-only-secret-please-change-32bytes-minimum"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 7 * 24 * 60  # 7 天

    # 登录安全：连续失败 login_max_failures 次后锁定 login_lock_minutes 分钟（数据词典"连续三次登录失败锁定"）
    login_max_failures: int = 3
    login_lock_minutes: int = 15

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- 预算与超支预测（阈值口径见 README）----
    budget_default_threshold: int = 80          # 默认预警阈值 80%
    forecast_high_risk_factor: float = 1.2      # 预测>120%预算 → 高超支风险

    # ---- 异常消费识别阈值（口径见 README）----
    anomaly_single_cents: int = 30000           # 单笔 > 300 元
    anomaly_single_factor: float = 3.0          # 或 > 3 倍近30天单笔均值（需≥5笔）
    anomaly_single_min_samples: int = 5
    anomaly_daily_factor: float = 2.0           # 当日 > 2 倍近30天日均
    anomaly_daily_floor_cents: int = 10000      # 且当日 > 100 元
    anomaly_window_days: int = 30

    # ---- 学期配置（可配置，报告按此划分学期）----
    semester_fall_start: str = "09-01"          # 秋季学期开始（MM-DD）
    semester_fall_end: str = "01-20"            # 秋季学期结束（次年 MM-DD）
    semester_spring_start: str = "02-20"
    semester_spring_end: str = "07-10"

    # ---- 外部 AI 服务（不配置则走本地演示模式，接口会明确标注）----
    ai_mode: str = "auto"                       # auto | demo | external
    ai_api_base_url: str = ""                   # OpenAI 兼容接口，如 https://api.openai.com/v1
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    speech_api_base_url: str = ""               # 语音转写（OpenAI 兼容 /audio/transcriptions）
    speech_api_key: str = ""
    speech_model: str = "whisper-1"
    ocr_api_base_url: str = ""                  # 图片识别（OpenAI 兼容 /chat/completions 多模态）
    ocr_api_key: str = ""
    ocr_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 20.0

    # ---- 报告导出 ----
    export_dir: str = "exports"  # PDF 导出目录（相对 backend 运行目录）

    # ---- 邮件（找回密码验证码；未配置时接口明确返回"未配置"）----
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    reset_code_minutes: int = 5                 # 验证码有效期 5 分钟

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_llm(self) -> bool:
        return bool(self.ai_api_base_url and self.ai_api_key)

    @property
    def has_speech(self) -> bool:
        return bool(self.speech_api_base_url and self.speech_api_key)

    @property
    def has_ocr(self) -> bool:
        return bool(self.ocr_api_base_url and self.ocr_api_key)

    @property
    def has_smtp(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.smtp_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()
