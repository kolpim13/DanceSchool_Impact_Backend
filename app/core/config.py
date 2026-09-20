import os
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///' + str(ROOT / 'data' / 'impact.db'))
    title: str = 'Impact Backend'

settings = Settings()
