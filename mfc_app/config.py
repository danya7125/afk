import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "mfc_data")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD")
    PG_CONNECT_TIMEOUT = int(os.getenv("PG_CONNECT_TIMEOUT", "5"))

    GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
    GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-3-Ultra")
    GIGACHAT_VERIFY_SSL = _as_bool(os.getenv("GIGACHAT_VERIFY_SSL"), default=False)

    CHAT_MAX_INPUT_CHARS = int(os.getenv("CHAT_MAX_INPUT_CHARS", "2000"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
