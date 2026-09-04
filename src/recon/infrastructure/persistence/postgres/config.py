from __future__ import annotations

import os 
from dataclasses import dataclass 
from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True, frozen=True, kw_only=True)
class DatabaseConfig:
    dsn: str

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        dsn = os.getenv("DATABASE_URL")

        if not dsn:
            raise RuntimeError("DATABASE_URL is not configured.")

        return cls(dsn=dsn)