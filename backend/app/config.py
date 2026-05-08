from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 含 app/、固定把相对路径的 sqlite 文件解析到此目录，避免从仓库根目录 / backend 启动时用到两份库。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_ROOT.parent


def _resolve_sqlite_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url
    rest = url[len("sqlite:///") :]
    if rest.startswith("/"):
        return f"sqlite:///{Path(rest).resolve()}"
    return f"sqlite:///{(_BACKEND_ROOT / rest).resolve()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_ROOT / ".env"), str(_REPO_ROOT / ".env")),
        env_file_encoding="utf-8",
    )

    app_name: str = "Word Practice API"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    database_url: str = "sqlite:///./word_practice.db"
    word_missing_ratio: float = Field(default=0.5, ge=0.1, le=0.9)
    # 所有业务路由挂载在此前缀下（环境变量 API_PREFIX），例如 /api 或 /api/v1
    api_prefix: str = "/api"
    # Dify / 自动化导入：`X-API-Key` 须与此一致（可用环境变量 DIFY_IMPORT_API_KEY 覆盖）
    dify_import_api_key: str = "dify"
    # 浏览器 Origin 与白名单匹配的跨域请求（含局域网用手机/电脑 IP 打开前端时直连 API）。
    # 勿在公网裸奔部署时继续用过宽的正则；可用环境变量覆盖为更严规则或空字符串关闭正则仅保留 allow_origins。
    cors_allow_origin_regex: str = Field(
        default=r"^https?://([\w.-]+|\d{1,3}(\.\d{1,3}){3})(:\d+)?$"
    )

    @model_validator(mode="after")
    def resolve_sqlite_path(self):
        url = self.database_url
        if url.startswith("sqlite:///"):
            object.__setattr__(self, "database_url", _resolve_sqlite_url(url))
        return self

    @model_validator(mode="after")
    def normalize_api_prefix(self):
        raw = (self.api_prefix or "/api").strip()
        if not raw.startswith("/"):
            raw = f"/{raw}"
        raw = raw.rstrip("/")
        if not raw:
            raw = "/api"
        object.__setattr__(self, "api_prefix", raw)
        return self


settings = Settings()
