"""Yenileme süreci iş kuralları.

PoliSoft'ta 'Yenileme Süreci' modülü bitişi yaklaşan poliçeleri döneme (MM-YYYY) göre havuza alır,
temsilci pozisyon (poz) ilerletir, şirketlerden teklif girer ve sonunda 'Yenilendi' / 'Kaybedildi' ile kapatır.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..utils import donem, logla


def surece_al(db: Session, gun: int, kullanici: Optional[models.Kullanici] = None) -> int:
    """Bitişine `gun` gün kalan, henüz süreçte olmayan aktif poliçeleri sürece alır. Eklenen kayıt sayısını döner."""
    bugun = date.today()
    sinir = bugun + timedelta(days=gun)
    mevcut = {r[0] for r in db.execute(select(models.YenilemeSureci.police_id).where(models.YenilemeSureci.police_id.isnot(None)))}
    q = select(models.Police).where(models.Police.durum == "Aktif", models.Police.bitis_tarihi <= sinir,
                                    models.Police.bitis_tarihi >= bugun - timedelta(days=15))
    eklenen = 0
    for p in db.scalars(q):
        if p.id in mevcut:
            continue
        s = models.YenilemeSureci(hesap_id=p.hesap_id, police_id=p.id, ana_brans_id=p.ana_brans_id,
                                  donem=donem(p.bitis_tarihi), bitis_tarihi=p.bitis_tarihi,
                                  temsilci_id=p.temsilci_id, pozisyon="Bekliyor")
        s.hareketler.append(models.YenilemeHareket(kullanici=kullanici.kullanici_adi if kullanici else "sistem",
                                                   pozisyon="Bekliyor", aciklama="Otomatik olarak sürece alındı"))
        db.add(s)
        eklenen += 1
    if eklenen:
        logla(db, kullanici, "Yenileme havuzu güncellendi", "yenileme", None, f"{eklenen} poliçe sürece alındı")
    return eklenen


def pozisyon_degistir(db: Session, s: models.YenilemeSureci, pozisyon: str, aciklama: str, kullanici: models.Kullanici,
                      sonuc_nedeni: str = "") -> None:
    s.pozisyon = pozisyon
    if pozisyon in ("Yenilendi", "Kaybedildi", "İptal"):
        s.kapanis_tarihi = date.today()
        s.sonuc_nedeni = sonuc_nedeni or aciklama
        if s.potansiyel is not None:
            s.potansiyel.durum = "Kazanıldı" if pozisyon == "Yenilendi" else "Kaybedildi"
    s.hareketler.append(models.YenilemeHareket(kullanici=kullanici.kullanici_adi, pozisyon=pozisyon, aciklama=aciklama))
    logla(db, kullanici, f"Yenileme pozisyonu: {pozisyon}", "yenileme", s.id, aciklama)


def yenile(db: Session, s: models.YenilemeSureci, yeni: models.Police, kullanici: models.Kullanici) -> None:
    """Süreçteki poliçeyi yeni poliçe ile kapatır; eskisini 'Yenilendi' durumuna çeker."""
    yeni.kaynak = "Yenileme"
    if s.police is not None:
        yeni.onceki_police_id = s.police.id
        yeni.yenileme_no = (s.police.yenileme_no or 0) + 1 if yeni.yenileme_no in (None, 0) else yeni.yenileme_no
        s.police.durum = "Yenilendi"
    db.add(yeni)
    db.flush()
    s.yeni_police_id = yeni.id
    pozisyon_degistir(db, s, "Yenilendi", f"Yeni poliçe: {yeni.police_no}", kullanici)


def ozet(db: Session, donem_kodu: Optional[str] = None) -> dict:
    """Dashboard için pozisyon bazlı sayılar."""
    q = select(models.YenilemeSureci.pozisyon, models.YenilemeSureci.id)
    if donem_kodu:
        q = q.where(models.YenilemeSureci.donem == donem_kodu)
    sayac = {p: 0 for p in models.YENILEME_POZISYONLARI}
    for poz, _ in db.execute(q):
        sayac[poz] = sayac.get(poz, 0) + 1
    kapanan = sayac["Yenilendi"] + sayac["Kaybedildi"]
    sayac["oran"] = round(100 * sayac["Yenilendi"] / kapanan, 1) if kapanan else 0.0
    return sayac
