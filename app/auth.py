"""Parola özetleme ve oturum yardımcıları (harici bağımlılık yok)."""
import hashlib
import hmac
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from . import models

_ITER = 200_000


def sifre_ozetle(sifre: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${salt.hex()}${dk.hex()}"


def sifre_dogrula(sifre: str, ozet: str) -> bool:
    try:
        _, iters, salt_hex, dk_hex = ozet.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def aktif_kullanici(request: Request, db: Session = Depends(get_db)) -> Optional[models.Kullanici]:
    uid = request.session.get("uid")
    if not uid:
        return None
    k = db.get(models.Kullanici, uid)
    if k is None or not k.aktif:
        request.session.clear()
        return None
    return k


class GirisGerekli(Exception):
    """Oturum yoksa /login'e yönlendirmek için kullanılır."""


def giris_gerekli(request: Request, db: Session = Depends(get_db)) -> models.Kullanici:
    k = aktif_kullanici(request, db)
    if k is None:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Giriş gerekli")
        raise GirisGerekli()
    request.state.kullanici = k
    return k


def yonetici_gerekli(k: models.Kullanici = Depends(giris_gerekli)) -> models.Kullanici:
    if k.rol not in ("admin", "yonetici"):
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    return k
