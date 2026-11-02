"""Uygulama ayarları. Tüm değerler ortam değişkenleriyle (veya .env dosyasıyla) ezilebilir."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _load_dotenv() -> None:
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "OpenAcente")
    # SQLite varsayılan; MySQL için: mysql+pymysql://user:pass@host/db  PostgreSQL için: postgresql+psycopg://...
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'openacente.db').as_posix()}")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "degistir-bunu-uretimde-cok-gizli-anahtar")
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))
    # Yenileme süreci: bitişine bu kadar gün kalan poliçeler otomatik sürece alınır
    YENILEME_GUN: int = int(os.getenv("YENILEME_GUN", "45"))
    # Mesaj sağlayıcısı: log | smtp | http_sms
    MESAJ_SAGLAYICI: str = os.getenv("MESAJ_SAGLAYICI", "log")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")
    SMS_HTTP_URL: str = os.getenv("SMS_HTTP_URL", "")
    SMS_HTTP_TOKEN: str = os.getenv("SMS_HTTP_TOKEN", "")
    SESSION_SURE_SN: int = int(os.getenv("SESSION_SURE_SN", str(8 * 3600)))
    DEMO_VERI: bool = os.getenv("DEMO_VERI", "1") == "1"


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
