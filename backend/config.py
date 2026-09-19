import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'civicfix.db'}")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SLA_HOURS = {
    "CRITICAL": int(os.getenv("SLA_HOURS_CRITICAL", 24)),
    "HIGH": int(os.getenv("SLA_HOURS_HIGH", 48)),
    "MEDIUM": int(os.getenv("SLA_HOURS_MEDIUM", 96)),
    "LOW": int(os.getenv("SLA_HOURS_LOW", 168)),
}

DUPLICATE_SIMILARITY_THRESHOLD = 0.42

AUTH_SECRET = os.getenv("AUTH_SECRET", "civicfix-dev-secret-change-me")
ACCESS_TOKEN_HOURS = int(os.getenv("ACCESS_TOKEN_HOURS", 12))
