"""Runtime configuration for Lioran."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "hermes3:8b")
    max_retries: int = min(3, max(1, int(os.getenv("MAX_RETRIES", "3"))))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    total_timeout: int = int(os.getenv("TOTAL_TIMEOUT", "90"))
    task_ttl_seconds: int = int(os.getenv("TASK_TTL_SECONDS", "3600"))


settings = Settings()
