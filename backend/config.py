import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'civicfix.db'}")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
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

OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", 5))
OTP_COOLDOWN_SECONDS = int(os.getenv("OTP_COOLDOWN_SECONDS", 30))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", 5))
OTP_PROVIDER = os.getenv("OTP_PROVIDER", "auto").strip().lower()
OTP_DEMO_MODE = os.getenv("OTP_DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}

# Twilio Verify credentials. Keep these only in local .env / Render secrets.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID", "").strip()

SLA_HOURS_CRITICAL = int(os.getenv("SLA_HOURS_CRITICAL", 24))
SLA_HOURS_HIGH = int(os.getenv("SLA_HOURS_HIGH", 48))
SLA_HOURS_MEDIUM = int(os.getenv("SLA_HOURS_MEDIUM", 96))
SLA_HOURS_LOW = int(os.getenv("SLA_HOURS_LOW", 168))
