from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    helicone_api_key: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/sharpness"
    redis_url: str = "redis://localhost:6379/0"

    probe_interval_minutes: int = 10
    alert_score_drop_threshold: int = 15
    context_warning_percent: int = 60

    models: str = "anthropic/claude-sonnet-4-5,openai/gpt-4o,x-ai/grok-2,google/gemini-2.0-flash"

    btc_volatility_exchange: str = "binance"
    volatility_window_minutes: int = 60

    @property
    def model_list(self) -> List[str]:
        return [m.strip() for m in self.models.split(",") if m.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
