"""Potansiyel satış (dış poliçeler) - PoliSoft 'frmDisPoliceListesi' karşılığı."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli
from ..database import get_db
from ..services import disa_aktar
from ..templating import render
from ..utils import flash, logla, para, tam, tarih
from .ortak import bos, bul, sayfala, secenekler

router = APIRouter(prefix="/potansiyel", tags=["potansiyel"])
DURUMLAR = ["Açık", "Sürece Alındı", "Kazanıldı", "Kaybedildi"]


def _sorgu(q: str, durum: str, ana_brans_id: Optional[int], temsilci_id: Optional[int]):
    P = models.Potansiyel
    s = select(P)
    if q:
        like = f"%{q}%"
        s = s.where(or_(P.unvan.like(like), P.plaka.like(like.upper()), P.tc_no.like(like), P.gsm.like(like), P.eski_police_no.like(like)))
    if durum:
        s = s.where(P.durum == durum)
    if ana_brans_id:
        s = s.where(P.ana_brans_id == ana_brans_id)
    if temsilci_id:
        s = s.where(P.temsilci_id == temsilci_id)
    return s.order_by(P.eski_bitis)


@router.get("")
def liste(request: Request, q: str = "", durum: str = "Açık", ana_brans_id: Optional[int] = None, temsilci_id: Optional[int] = None, sayfa: int = 1,
          k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    sonuc = sayfala(db, _sorgu(q, durum, ana_brans_id, temsilci_id), sayfa)
    return render(request, "potansiyel/liste.html", **sonuc, q=q, durum=durum, ana_brans_id=ana_brans_id, temsilci_id=temsilci_id,
                  DURUMLAR=DURUMLAR, **secenekler(db))


@router.get("/disa-aktar")
def disa(q: str = "", durum: str = "", ana_brans_id: Optional[int] = None, temsilci_id: Optional[int] = None,
         k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    kayitlar = db.scalars(_sorgu(q, durum, ana_brans_id, temsilci_id)).all()
    kolon = ["Ünvan", "TC/VKN", "GSM", "Branş", "Eski Şirket", "Eski Poliçe", "Eski Bitiş", "Eski Brüt", "Plaka", "Araç", "Temsilci", "Durum", "Kaynak"]
    satir = [(p.unvan, p.tc_no or p.vergi_no, p.gsm, p.ana_brans.ad, p.eski_sirket, p.eski_police_no, p.eski_bitis, p.eski_brut_prim, p.plaka,
              f"{p.marka or ''} {p.model or ''} {p.model_yili or ''}".strip(), p.temsilci.ad_soyad if p.temsilci else "", p.durum, p.kaynak) for p in kayitlar]
    return Response(disa_aktar.excel_bytes("Potansiyel", kolon, satir), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=potansiyel_{date.today()}.xlsx"})


@router.get("/yeni")
def yeni_form(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    return render(request, "potansiyel/form.html", p=None, **secenekler(db))


def _formdan(p: models.Potansiyel, f: dict) -> Optional[str]:
    p.unvan = (f.get("unvan") or "").strip()
    if not p.unvan:
        return "Ünvan zorunludur."
    p.ana_brans_id = tam(f.get("ana_brans_id"))
    if not p.ana_brans_id:
        return "Branş seçin."
    for alan in ("tc_no", "vergi_no", "gsm", "telefon", "eposta", "il", "ilce", "adres", "eski_sirket", "eski_acente", "eski_police_no", "marka", "model", "aciklama", "kaynak"):
        setattr(p, alan, bos(f.get(alan)))
    p.plaka = (f.get("plaka") or "").upper().replace(" ", "") or None
    p.model_yili = tam(f.get("model_yili"))
    p.eski_tanzim = tarih(f.get("eski_tanzim"))
    p.eski_baslama = tarih(f.get("eski_baslama"))
    p.eski_bitis = tarih(f.get("eski_bitis"))
    p.eski_brut_prim = para(f.get("eski_brut_prim"))
    p.temsilci_id = tam(f.get("temsilci_id"))
    p.kaynak = p.kaynak or "Manuel"
    if f.get("durum") in DURUMLAR:
        p.durum = f["durum"]
    return None


@router.post("/yeni")
async def yeni(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = dict(await request.form())
    p = models.Potansiyel(olusturan=k.kullanici_adi)
    hata = _formdan(p, f)
    if hata:
        flash(request, hata, "hata")
        return render(request, "potansiyel/form.html", p=p, **secenekler(db))
    db.add(p)
    db.flush()
    logla(db, k, "Potansiyel kaydı açıldı", "potansiyel", p.id, p.unvan)
    db.commit()
    flash(request, "Potansiyel kaydı oluşturuldu.")
    return RedirectResponse("/potansiyel", status_code=303)


@router.get("/{pid}/duzenle")
def duzenle_form(request: Request, pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Potansiyel, pid, "Potansiyel")
    return render(request, "potansiyel/form.html", p=p, **secenekler(db))


@router.post("/{pid}/duzenle")
async def duzenle(request: Request, pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Potansiyel, pid, "Potansiyel")
    hata = _formdan(p, dict(await request.form()))
    if hata:
        flash(request, hata, "hata")
        return render(request, "potansiyel/form.html", p=p, **secenekler(db))
    db.commit()
    flash(request, "Kayıt güncellendi.")
    return RedirectResponse("/potansiyel", status_code=303)


@router.post("/{pid}/sil")
def sil(pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Potansiyel, pid, "Potansiyel")
    if not db.scalar(select(models.YenilemeSureci.id).where(models.YenilemeSureci.potansiyel_id == pid)):
        db.delete(p)
        db.commit()
    return RedirectResponse("/potansiyel", status_code=303)
