"""Jinja2 şablon motoru ve ortak bağlam."""
from datetime import date, datetime
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import __version__, models
from .config import settings
from .utils import donem, flash_al, tl, tr_tarih

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["tl"] = tl
templates.env.filters["tarih"] = tr_tarih
templates.env.filters["donem"] = donem
templates.env.globals.update(
    APP_NAME=settings.APP_NAME,
    VERSION=__version__,
    bugun=date.today,
    simdi=datetime.now,
    POZISYONLAR=models.YENILEME_POZISYONLARI,
)

MENU = [
    ("/", "Dashboard", "⌂"),
    ("/hesaplar", "Hesap Kartları", "👤"),
    ("/policeler", "Poliçeler", "📄"),
    ("/yenileme", "Yenileme Süreci", "🔁"),
    ("/potansiyel", "Potansiyel Satış", "🎯"),
    ("/tahsilat", "Tahsilat", "₺"),
    ("/ajanda", "Ajanda", "📅"),
    ("/talepler", "Talepler", "📨"),
    ("/mesajlar", "Mesajlar", "💬"),
    ("/raporlar", "Raporlar", "📊"),
    ("/tanimlar", "Tanımlar", "⚙"),
]


def render(request: Request, sablon: str, status_code: int = 200, **ctx):
    ctx.setdefault("kullanici", getattr(request.state, "kullanici", None))
    ctx["flashlar"] = flash_al(request)
    ctx["menu"] = MENU
    ctx["yol"] = request.url.path
    return templates.TemplateResponse(request, sablon, ctx, status_code=status_code)
