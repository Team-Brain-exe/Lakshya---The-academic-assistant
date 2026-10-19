import os

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(_env_path)


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _convert_db_url(url: str) -> str:
    """Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL: str = _convert_db_url(_require("DATABASE_URL"))
SESSION_SECRET: str = _require("SESSION_SECRET")
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
ATTEMPT_RULE: str = os.getenv("ATTEMPT_RULE", "best")
MAX_ATTEMPTS: int = int(os.getenv("MAX_ATTEMPTS", "2"))
