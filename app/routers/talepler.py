"""Müşteri talepleri (hasar, zeyil, bilgi...) - PoliSoft 'frmTalepGirisi' / 'frmTalepListe' karşılığı."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli
from ..database import get_db
from ..templating import render
from ..utils import flash, logla, tam
from .ortak import bos, bul, sayfala, secenekler

router = APIRouter(prefix="/talepler", tags=["talepler"])
TURLER = ["Hasar", "Zeyil", "İptal", "Bilgi", "Ödeme", "Şikayet", "Evrak", "Diğer"]
DURUMLAR = ["Açık", "İşlemde", "Kapandı"]


@router.get("")
def liste(request: Request, durum: str = "", talep_turu: str = "", temsilci_id: Optional[int] = None, sayfa: int = 1,
          k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    T = models.Talep
    s = select(T).options(selectinload(T.hesap), selectinload(T.police), selectinload(T.temsilci))
    if durum:
        s = s.where(T.durum == durum)
    else:
        s = s.where(T.durum != "Kapandı")
    if talep_turu:
        s = s.where(T.talep_turu == talep_turu)
    if temsilci_id:
        s = s.where(T.temsilci_id == temsilci_id)
    sonuc = sayfala(db, s.order_by(T.id.desc()), sayfa)
    return render(request, "talepler/liste.html", **sonuc, durum=durum, talep_turu=talep_turu, temsilci_id=temsilci_id, TURLER=TURLER, DURUMLAR=DURUMLAR, **secenekler(db))


@router.get("/yeni")
def yeni_form(request: Request, hesap_id: Optional[int] = None, police_id: Optional[int] = None, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    hesap = db.get(models.Hesap, hesap_id) if hesap_id else None
    return render(request, "talepler/form.html", hesap=hesap, police_id=police_id, TURLER=TURLER, **secenekler(db))


@router.post("/yeni")
def yeni(request: Request, hesap_id: int = Form(...), police_id: str = Form(""), talep_turu: str = Form(...), aciklama: str = Form(...),
         temsilci_id: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hesap_id, "Hesap")
    t = models.Talep(hesap_id=h.id, police_id=tam(police_id), talep_turu=talep_turu, aciklama=aciklama.strip(),
                     temsilci_id=tam(temsilci_id) or h.temsilci_id, olusturan=k.kullanici_adi)
    t.hareketler.append(models.TalepHareket(kullanici=k.kullanici_adi, durum="Açık", aciklama="Talep açıldı"))
    db.add(t)
    db.flush()
    logla(db, k, f"Talep açıldı: {talep_turu}", "hesap", h.id, aciklama[:200])
    db.commit()
    flash(request, "Talep kaydedildi.")
    return RedirectResponse(f"/talepler/{t.id}", status_code=303)


@router.get("/{tid}")
def detay(request: Request, tid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    t = bul(db, models.Talep, tid, "Talep")
    dosyalar = list(db.scalars(select(models.Dosya).where(models.Dosya.yer == "talep", models.Dosya.yer_id == tid)))
    return render(request, "talepler/detay.html", t=t, dosyalar=dosyalar, DURUMLAR=DURUMLAR, **secenekler(db))


@router.post("/{tid}/hareket")
def hareket(request: Request, tid: int, durum: str = Form(...), aciklama: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    t = bul(db, models.Talep, tid, "Talep")
    if durum in DURUMLAR:
        t.durum = durum
        t.durum_aciklama = bos(aciklama) or t.durum_aciklama
        t.kapanis = datetime.now() if durum == "Kapandı" else None
    t.hareketler.append(models.TalepHareket(kullanici=k.kullanici_adi, durum=t.durum, aciklama=bos(aciklama) or f"Durum: {t.durum}"))
    logla(db, k, f"Talep {t.durum.lower()}", "hesap", t.hesap_id, f"#{t.id} {t.talep_turu}")
    db.commit()
    return RedirectResponse(f"/talepler/{tid}", status_code=303)
