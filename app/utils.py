"""Küçük yardımcılar: tarih çözümleme, para biçimi, flash mesajları, log."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from . import models


def tarih(v: Optional[str]) -> Optional[date]:
    if not v:
        return None
    v = v.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def para(v) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = str(v).strip().replace(" ", "")
    # 1.234,56 (TR) veya 1234.56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def tam(v, varsayilan: Optional[int] = None) -> Optional[int]:
    try:
        return int(v) if v not in (None, "") else varsayilan
    except (TypeError, ValueError):
        return varsayilan


def tl(v) -> str:
    """1234.5 -> '1.234,50'"""
    try:
        d = Decimal(str(v or 0))
    except InvalidOperation:
        return "0,00"
    s = f"{d:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def tr_tarih(v) -> str:
    if not v:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d.%m.%Y %H:%M")
    return v.strftime("%d.%m.%Y")


def donem(d: Optional[date]) -> str:
    """PoliSoft'taki 'ydonem' mantığı: MM-YYYY"""
    return f"{d.month:02d}-{d.year}" if d else ""


def flash(request: Request, mesaj: str, tur: str = "basari") -> None:
    request.session.setdefault("_flash", []).append({"mesaj": mesaj, "tur": tur})


def flash_al(request: Request):
    return request.session.pop("_flash", [])


def logla(db: Session, kullanici: Optional[models.Kullanici], islem: str, yer: str = "", yer_id: Optional[int] = None, aciklama: str = "") -> None:
    db.add(models.IslemLog(kullanici=kullanici.kullanici_adi if kullanici else "sistem", islem=islem, yer=yer, yer_id=yer_id, aciklama=aciklama[:1000]))
