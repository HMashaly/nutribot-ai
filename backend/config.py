from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = ""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "nutrition"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    usda_api_key: str = "DEMO_KEY"
    mistral_api_key: str = ""
    session_max_hours: int = 8
    moderation_model: str = "mistral-moderation-2411"

    # ── Observability ──────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "console"  # "console" (human-readable) or "json" (structured)

    # LangSmith tracing — stays off unless explicitly enabled and keyed.
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "nutribot"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # ── Abuse protection ───────────────────────────────────────────────────────
    chat_rate_limit_per_minute: int = 20
    agent_cache_max: int = 256

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()  # type: ignore[call-arg]
