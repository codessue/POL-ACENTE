"""Tahsilat / taksit takibi - PoliSoft 'PBS - Tahsilat' karşılığı."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli, yonetici_gerekli
from ..database import get_db
from ..services import disa_aktar
from ..templating import render
from ..utils import flash, logla, para, tarih
from .ortak import bos, bul, sayfala, secenekler

router = APIRouter(prefix="/tahsilat", tags=["tahsilat"])
SEKILLER = ["Nakit", "Kredi Kartı", "Havale/EFT", "Çek", "Senet"]


@router.get("")
def liste(request: Request, gorunum: str = "vadesi", temsilci_id: Optional[int] = None, t1: str = "", t2: str = "", sayfa: int = 1,
          k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    bugun = date.today()
    T, P = models.Taksit, models.Police
    if gorunum == "tahsilatlar":
        s = select(models.Tahsilat).options(selectinload(models.Tahsilat.police), selectinload(models.Tahsilat.hesap))
        d1, d2 = tarih(t1), tarih(t2)
        if d1:
            s = s.where(models.Tahsilat.tarih >= d1)
        if d2:
            s = s.where(models.Tahsilat.tarih <= d2)
        sonuc = sayfala(db, s.order_by(models.Tahsilat.tarih.desc(), models.Tahsilat.id.desc()), sayfa)
        toplam = sum((Decimal(str(t.tutar)) for t in sonuc["kayitlar"] if t.durum == "Tahsil Edildi"), Decimal("0"))
        return render(request, "tahsilat/liste.html", gorunum=gorunum, **sonuc, para_toplam=toplam, t1=t1, t2=t2, temsilci_id=temsilci_id, SEKILLER=SEKILLER, **secenekler(db))
    s = select(T).join(P).options(selectinload(T.police).selectinload(P.hesap), selectinload(T.police).selectinload(P.sirket)).where(T.odendi.is_(False), P.durum == "Aktif")
    if gorunum == "vadesi":
        s = s.where(T.vade < bugun)
    elif gorunum == "yaklasan":
        s = s.where(T.vade.between(bugun, bugun + timedelta(days=15)))
    if temsilci_id:
        s = s.where(P.temsilci_id == temsilci_id)
    sonuc = sayfala(db, s.order_by(T.vade), sayfa)
    toplam = sum((Decimal(str(t.tutar)) for t in sonuc["kayitlar"]), Decimal("0"))
    return render(request, "tahsilat/liste.html", gorunum=gorunum, **sonuc, para_toplam=toplam, t1=t1, t2=t2, temsilci_id=temsilci_id, SEKILLER=SEKILLER, **secenekler(db))


@router.get("/disa-aktar")
def disa(gorunum: str = "vadesi", k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    bugun = date.today()
    T, P = models.Taksit, models.Police
    s = select(T).join(P).where(T.odendi.is_(False), P.durum == "Aktif")
    if gorunum == "vadesi":
        s = s.where(T.vade < bugun)
    kayitlar = db.scalars(s.order_by(T.vade)).all()
    kolon = ["Vade", "Gecikme (gün)", "Taksit", "Tutar", "Poliçe No", "Şirket", "Sigortalı", "GSM", "Temsilci"]
    satir = [(t.vade, (bugun - t.vade).days, f"{t.sira}/{t.police.taksit_sayisi}", t.tutar, t.police.police_no, t.police.sirket.ad,
              t.police.hesap.unvan, t.police.hesap.gsm, t.police.temsilci.ad_soyad if t.police.temsilci else "") for t in kayitlar]
    return Response(disa_aktar.excel_bytes("Tahsilat", kolon, satir), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=tahsilat_{gorunum}_{date.today()}.xlsx"})


@router.post("/taksit/{tid}/ode")
def taksit_ode(request: Request, tid: int, tahsilat_sekli: str = Form("Nakit"), tarih_: str = Form("", alias="tarih"), makbuz_no: str = Form(""),
               k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    t = bul(db, models.Taksit, tid, "Taksit")
    if t.odendi:
        flash(request, "Taksit zaten ödenmiş.", "bilgi")
    else:
        t.odendi = True
        t.odeme_tarihi = tarih(tarih_) or date.today()
        db.add(models.Tahsilat(police_id=t.police_id, hesap_id=t.police.hesap_id, tarih=t.odeme_tarihi, tutar=t.tutar, tahsilat_sekli=tahsilat_sekli,
                               makbuz_no=bos(makbuz_no), aciklama=f"{t.sira}. taksit", kullanici=k.kullanici_adi))
        logla(db, k, "Taksit tahsil edildi", "police", t.police_id, f"{t.sira}. taksit {t.tutar}")
        db.commit()
        flash(request, "Tahsilat kaydedildi.")
    geri = request.headers.get("referer") or f"/policeler/{t.police_id}"
    return RedirectResponse(geri, status_code=303)


@router.post("/police/{pid}")
def serbest_tahsilat(request: Request, pid: int, tutar: str = Form(...), tahsilat_sekli: str = Form("Nakit"), tarih_: str = Form("", alias="tarih"),
                     makbuz_no: str = Form(""), aciklama: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    tut = para(tutar)
    if tut <= 0:
        flash(request, "Tutar sıfırdan büyük olmalı.", "hata")
        return RedirectResponse(f"/policeler/{pid}", status_code=303)
    db.add(models.Tahsilat(police_id=pid, hesap_id=p.hesap_id, tarih=tarih(tarih_) or date.today(), tutar=tut, tahsilat_sekli=tahsilat_sekli,
                           makbuz_no=bos(makbuz_no), aciklama=bos(aciklama), kullanici=k.kullanici_adi))
    # tutarı açık taksitlere sırayla kapat
    kalan = tut
    for t in p.taksitler:
        if t.odendi or kalan <= 0:
            continue
        if kalan >= Decimal(str(t.tutar)):
            t.odendi, t.odeme_tarihi = True, date.today()
            kalan -= Decimal(str(t.tutar))
    logla(db, k, "Tahsilat girildi", "police", pid, f"{tut} {tahsilat_sekli}")
    db.commit()
    flash(request, "Tahsilat kaydedildi.")
    return RedirectResponse(f"/policeler/{pid}", status_code=303)


@router.post("/{tid}/iade")
def iade(request: Request, tid: int, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    t = bul(db, models.Tahsilat, tid, "Tahsilat")
    t.durum = "İade"
    logla(db, k, "Tahsilat iade edildi", "police", t.police_id, str(t.tutar))
    db.commit()
    return RedirectResponse(request.headers.get("referer") or "/tahsilat?gorunum=tahsilatlar", status_code=303)
