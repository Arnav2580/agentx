import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_ENV = Path.home() / ".juror" / ".env"
LOCAL_ENV = PROJECT_ROOT / ".env"

if GLOBAL_ENV.exists():
    load_dotenv(GLOBAL_ENV, override=False)
if LOCAL_ENV.exists():
    load_dotenv(LOCAL_ENV, override=False)


class Config:
    def __init__(self) -> None:
        juror_home = Path.home() / ".juror"
        default_db = juror_home / "verdicts.db"
        default_log = juror_home / "juror.log"

        gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GROK_API_KEY", "").strip()
        self.GEMINI_API_KEY: str = gemini_key
        self.GROK_API_KEY: str = gemini_key
        self.MODEL: str = os.getenv("MODEL", "gemini-2.5-flash")
        self.MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "400"))
        self.SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
        self.SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
        self.DB_PATH: str = os.getenv("DB_PATH", str(default_db))
        self.LOG_PATH: str = os.getenv("LOG_PATH", str(default_log))

        self.APPROVED_THRESHOLD: int = int(os.getenv("APPROVED_THRESHOLD", "1"))
        self.FLAGGED_THRESHOLD: int = int(os.getenv("FLAGGED_THRESHOLD", "2"))
        self.BLOCKED_THRESHOLD: int = int(os.getenv("BLOCKED_THRESHOLD", "3"))
        self.AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "30"))

        self.REQUEST_CHAR_LIMIT: int = int(os.getenv("REQUEST_CHAR_LIMIT", "8000"))


config = Config()
