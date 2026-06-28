from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    # Cerebras free API
    cerebras_api_key: str = ""

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # SQLite — stored locally, no server
    database_url: str = "sqlite:///./data/sharpness.db"

    # Probe config
    probe_interval_minutes: int = 15
    alert_score_drop_threshold: int = 15
    context_warning_percent: int = 60

    # Cerebras free models
    models: str = "llama-3.3-70b,llama-3.1-8b"

    # BTC market data (Binance public, no key needed)
    btc_volatility_exchange: str = "binance"
    volatility_window_minutes: int = 60
    btc_volatility_high_threshold: float = 1.0
    btc_volatility_extreme_threshold: float = 2.0

    @property
    def model_list(self) -> List[str]:
        return [m.strip() for m in self.models.split(",") if m.strip()]

    class Config:
        env_file = ".env"


settings = Settings()

# Ensure data directory exists for SQLite
Path("data").mkdir(exist_ok=True)
