import os
import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

env_path = Path(__file__).resolve().parents[2] / ".env.secret" #C:\F Drive\KU Leuven\TrendTracker\trendtracker-earningcall-transcripts\.env
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    APP_NAME: str = os.environ.get("APP_NAME", "TrendTracker-Himanshu")

    DB_USER: str  
    DB_PASSWORD: str  
    DB_NAME: str  
    DB_HOST: str 
    DB_PORT: str 

    @property
    def DATABASE_URL(self) -> str:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            return database_url
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    CORS_ORIGINS: str

    SPACY_MODEL: str

    OPENFIGI_API_BASE_URL : str
    OPENFIGI_API_KEY : str

    CHUNK_STRATEGY: str
    EMBEDDING_MODEL: str
    USE_HYBRID_FTS: bool
    FTS_CANDIDATE_LIMIT: int

    TOP_K: int
    MIN_SCORE: float
    MAX_CONTEXT_CHARS: int

    REQUEST_TIMEOUT_SEC: int
    LLM_PROVIDER: str
    OLLAMA_BASE_URL: str
    OLLAMA_MODEL: str
    OPENAI_BASE_URL: str
    OPENAI_MODEL: str
    OPENAI_API_KEY: str

@lru_cache()
def get_settings() -> Settings:
    return Settings()