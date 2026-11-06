import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "Super Admin")

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_PATH = os.environ.get("COOKIE_PATH", "/")
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "30"))
REFRESH_TOKEN_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", "7"))

UPLOAD_DIR = Path(os.environ["UPLOAD_DIR"])
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR") or str(UPLOAD_DIR.parent / "backups"))

WHATSAPP_MODE = os.environ.get("WHATSAPP_MODE", "simulation").lower()
FONNTE_API_URL = os.environ.get("FONNTE_API_URL", "https://api.fonnte.com/send")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN", "").strip()
FONNTE_ADMIN_WA = [w.strip() for w in os.environ.get("FONNTE_ADMIN_WA", "").split(",") if w.strip()]
FONNTE_GROUP_ID = os.environ.get("FONNTE_GROUP_ID", "").strip()
FONNTE_WEBHOOK_SECRET = os.environ.get("FONNTE_WEBHOOK_SECRET", "").strip()
NOTIF_MAX_ATTEMPTS = int(os.environ.get("NOTIF_MAX_ATTEMPTS", "5"))
