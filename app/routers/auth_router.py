from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli, sifre_dogrula, sifre_ozetle
from ..database import get_db
from ..templating import render
from ..utils import flash, logla

router = APIRouter(tags=["auth"])


@router.get("/login")
def login_form(request: Request, sonraki: str = "/"):
    if request.session.get("uid"):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", sonraki=sonraki, hata=None)


@router.post("/login")
def login(request: Request, kullanici_adi: str = Form(...), sifre: str = Form(...), sonraki: str = Form("/"),
          db: Session = Depends(get_db)):
    k = db.scalar(select(models.Kullanici).where(models.Kullanici.kullanici_adi == kullanici_adi.strip().lower()))
    if k is None or not k.aktif or not sifre_dogrula(sifre, k.sifre_hash):
        logla(db, None, "Başarısız giriş", "auth", None, kullanici_adi)
        db.commit()
        return render(request, "login.html", sonraki=sonraki, hata="Kullanıcı adı veya parola hatalı.")
    request.session["uid"] = k.id
    logla(db, k, "Giriş yapıldı", "auth")
    db.commit()
    if not sonraki.startswith("/") or sonraki.startswith("//"):
        sonraki = "/"
    return RedirectResponse(sonraki, status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/sifre")
def sifre_form(request: Request, k: models.Kullanici = Depends(giris_gerekli)):
    return render(request, "sifre.html")


@router.post("/sifre")
def sifre_degistir(request: Request, eski: str = Form(...), yeni: str = Form(...), yeni2: str = Form(...),
                   k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    if not sifre_dogrula(eski, k.sifre_hash):
        flash(request, "Mevcut parola hatalı.", "hata")
    elif yeni != yeni2 or len(yeni) < 6:
        flash(request, "Yeni parolalar eşleşmiyor veya 6 karakterden kısa.", "hata")
    else:
        db.get(models.Kullanici, k.id).sifre_hash = sifre_ozetle(yeni)
        logla(db, k, "Parola değiştirildi", "auth")
        db.commit()
        flash(request, "Parolanız güncellendi.")
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/sifre", status_code=303)
