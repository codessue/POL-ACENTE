"""Yenileme süreci - PoliSoft 'Yenileme - Satış' / 'frmYenilemeDetay' / 'frmTeklif' karşılığı."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli
from ..config import settings
from ..database import get_db
from ..services import yenileme_servisi
from ..templating import render
from ..utils import donem, flash, logla, para, tam, tarih
from .ortak import bos, bul, parametre, secenekler

router = APIRouter(prefix="/yenileme", tags=["yenileme"])


def _donemler(db: Session):
    return [r[0] for r in db.execute(select(models.YenilemeSureci.donem).distinct()) if r[0]]


def _donem_sirala(d: str):
    ay, yil = d.split("-")
    return (int(yil), int(ay))


@router.get("")
def pano(request: Request, donem_kodu: str = "", temsilci_id: Optional[int] = None, ana_brans_id: Optional[int] = None,
         gorunum: str = "pano", pozisyon: str = "", k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    S = models.YenilemeSureci
    donemler = sorted(_donemler(db), key=_donem_sirala)
    if not donem_kodu:
        donem_kodu = donem(date.today()) if donem(date.today()) in donemler or not donemler else donemler[-1]
    s = select(S).options(selectinload(S.hesap), selectinload(S.police), selectinload(S.ana_brans), selectinload(S.temsilci), selectinload(S.teklifler))
    if donem_kodu != "tum":
        s = s.where(S.donem == donem_kodu)
    if temsilci_id:
        s = s.where(S.temsilci_id == temsilci_id)
    if ana_brans_id:
        s = s.where(S.ana_brans_id == ana_brans_id)
    if pozisyon:
        s = s.where(S.pozisyon == pozisyon)
    kayitlar = list(db.scalars(s.order_by(S.bitis_tarihi)))
    kolonlar = {p: [x for x in kayitlar if x.pozisyon == p] for p in models.YENILEME_POZISYONLARI}
    ozet = yenileme_servisi.ozet(db, None if donem_kodu == "tum" else donem_kodu)
    return render(request, "yenileme/pano.html", kayitlar=kayitlar, kolonlar=kolonlar, donemler=donemler, donem_kodu=donem_kodu,
                  temsilci_id=temsilci_id, ana_brans_id=ana_brans_id, gorunum=gorunum, pozisyon=pozisyon, ozet=ozet,
                  yenileme_gun=settings.YENILEME_GUN, **secenekler(db))


@router.post("/havuzu-guncelle")
def havuz(request: Request, gun: int = Form(settings.YENILEME_GUN), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    n = yenileme_servisi.surece_al(db, gun, k)
    db.commit()
    flash(request, f"{n} poliçe yenileme sürecine alındı." if n else "Sürece alınacak yeni poliçe yok.", "bilgi")
    return RedirectResponse("/yenileme", status_code=303)


@router.get("/{sid}")
def detay(request: Request, sid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.YenilemeSureci, sid, "Süreç")
    oran = parametre(db, "varsayilan_komisyon_orani", "15")
    return render(request, "yenileme/detay.html", s=s, oran=oran, **secenekler(db))


@router.post("/{sid}/pozisyon")
def pozisyon(request: Request, sid: int, pozisyon: str = Form(...), aciklama: str = Form(""), sonuc_nedeni: str = Form(""),
             k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.YenilemeSureci, sid, "Süreç")
    if pozisyon not in models.YENILEME_POZISYONLARI:
        flash(request, "Geçersiz pozisyon.", "hata")
    elif pozisyon == "Yenilendi" and s.yeni_police_id is None:
        return RedirectResponse(f"/policeler/yeni?surec_id={sid}", status_code=303)
    else:
        yenileme_servisi.pozisyon_degistir(db, s, pozisyon, bos(aciklama) or f"Pozisyon {pozisyon} olarak güncellendi", k, sonuc_nedeni)
        db.commit()
        flash(request, f"Pozisyon: {pozisyon}")
    return RedirectResponse(f"/yenileme/{sid}", status_code=303)


@router.post("/{sid}/not")
def not_ekle(sid: int, aciklama: str = Form(...), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.YenilemeSureci, sid, "Süreç")
    s.hareketler.append(models.YenilemeHareket(kullanici=k.kullanici_adi, pozisyon=s.pozisyon, aciklama=aciklama.strip()[:500]))
    db.commit()
    return RedirectResponse(f"/yenileme/{sid}", status_code=303)


@router.post("/{sid}/temsilci")
def temsilci(sid: int, temsilci_id: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.YenilemeSureci, sid, "Süreç")
    s.temsilci_id = tam(temsilci_id)
    s.hareketler.append(models.YenilemeHareket(kullanici=k.kullanici_adi, pozisyon=s.pozisyon,
                                               aciklama=f"Temsilci atandı: {s.temsilci.ad_soyad if s.temsilci else '-'}"))
    db.commit()
    return RedirectResponse(f"/yenileme/{sid}", status_code=303)


@router.post("/{sid}/teklif")
def teklif_ekle(request: Request, sid: int, sirket_id: int = Form(...), teklif_no: str = Form(""), brut_prim: str = Form("0"),
                net_prim: str = Form(""), komisyon: str = Form(""), odeme_tipi: str = Form("Peşin"), taksit_sayisi: str = Form("1"),
                aciklama: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.YenilemeSureci, sid, "Süreç")
    brut = para(brut_prim)
    net = para(net_prim) if net_prim else brut
    kom = para(komisyon) if komisyon else (net * para(parametre(db, "varsayilan_komisyon_orani", "15")) / 100).quantize(para("0.01"))
    s.teklifler.append(models.Teklif(sirket_id=sirket_id, teklif_no=bos(teklif_no), brut_prim=brut, net_prim=net, komisyon=kom,
                                     odeme_tipi=odeme_tipi, taksit_sayisi=tam(taksit_sayisi, 1), aciklama=bos(aciklama), kullanici=k.kullanici_adi))
    if s.pozisyon in ("Bekliyor", "Arandı"):
        yenileme_servisi.pozisyon_degistir(db, s, "Teklif Alındı", "İlk teklif girildi", k)
    logla(db, k, "Teklif girildi", "yenileme", sid, f"{brut} TL")
    db.commit()
    return RedirectResponse(f"/yenileme/{sid}", status_code=303)


@router.post("/{sid}/teklif/{tid}/sec")
def teklif_sec(sid: int, tid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.YenilemeSureci, sid, "Süreç")
    for t in s.teklifler:
        t.secildi = (t.id == tid)
    if s.pozisyon == "Teklif Alındı":
        yenileme_servisi.pozisyon_degistir(db, s, "Teklif Sunuldu", "Teklif müşteriye sunuldu", k)
    db.commit()
    return RedirectResponse(f"/yenileme/{sid}", status_code=303)


@router.post("/{sid}/teklif/{tid}/sil")
def teklif_sil(sid: int, tid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    t = db.get(models.Teklif, tid)
    if t and t.surec_id == sid:
        db.delete(t)
        db.commit()
    return RedirectResponse(f"/yenileme/{sid}", status_code=303)


@router.post("/potansiyelden/{pot_id}")
def potansiyelden(request: Request, pot_id: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    """Potansiyel kaydını hesap kartına bağlayıp satış sürecine alır."""
    pot = bul(db, models.Potansiyel, pot_id, "Potansiyel")
    if pot.hesap_id is None:
        from ..services.disa_aktar import yeni_hes_kod
        h = None
        if pot.tc_no:
            h = db.scalar(select(models.Hesap).where(models.Hesap.tc_no == pot.tc_no))
        if h is None and pot.vergi_no:
            h = db.scalar(select(models.Hesap).where(models.Hesap.vergi_no == pot.vergi_no))
        if h is None:
            h = models.Hesap(hes_kod=yeni_hes_kod(db), unvan=pot.unvan, tc_no=pot.tc_no, vergi_no=pot.vergi_no, il=pot.il, ilce=pot.ilce,
                             adres=pot.adres, temsilci_id=pot.temsilci_id, tip="Kurumsal" if pot.vergi_no and not pot.tc_no else "Bireysel",
                             olusturan=k.kullanici_adi)
            if pot.gsm:
                h.telefonlar.append(models.HesapTelefon(tip="GSM", numara=pot.gsm))
            if pot.eposta:
                h.epostalar.append(models.HesapEposta(adres=pot.eposta))
            if pot.plaka:
                h.araclar.append(models.Arac(plaka=pot.plaka, marka=pot.marka, model=pot.model, model_yili=pot.model_yili))
            db.add(h)
            db.flush()
        pot.hesap_id = h.id
    s = models.YenilemeSureci(hesap_id=pot.hesap_id, potansiyel_id=pot.id, ana_brans_id=pot.ana_brans_id,
                              bitis_tarihi=pot.eski_bitis or date.today(), donem=donem(pot.eski_bitis or date.today()),
                              temsilci_id=pot.temsilci_id, pozisyon="Bekliyor")
    s.hareketler.append(models.YenilemeHareket(kullanici=k.kullanici_adi, pozisyon="Bekliyor", aciklama="Potansiyel satış sürece alındı"))
    pot.durum = "Sürece Alındı"
    db.add(s)
    db.flush()
    logla(db, k, "Potansiyel sürece alındı", "potansiyel", pot.id)
    db.commit()
    return RedirectResponse(f"/yenileme/{s.id}", status_code=303)
