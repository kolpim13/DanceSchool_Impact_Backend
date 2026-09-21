import os
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///' + str(ROOT / 'data' / 'impact.db'))
    title: str = 'Impact Backend'
    environment: str = os.getenv('APP_ENV', 'production').strip().lower()
    session_days: int = int(os.getenv('SESSION_DAYS', '7'))
    website_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv('WEBSITE_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
        if origin.strip()
    )

settings = Settings()
