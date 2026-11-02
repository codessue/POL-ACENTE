"""Router'ların ortak kullandığı küçük yardımcılar."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models

SAYFA_BOYU = 50


def secenekler(db: Session) -> dict:
    return {
        "temsilciler": list(db.scalars(select(models.Temsilci).where(models.Temsilci.aktif.is_(True)).order_by(models.Temsilci.ad_soyad))),
        "sirketler": list(db.scalars(select(models.SigortaSirketi).where(models.SigortaSirketi.aktif.is_(True)).order_by(models.SigortaSirketi.ad))),
        "branslar": list(db.scalars(select(models.AnaBrans).order_by(models.AnaBrans.sira, models.AnaBrans.ad))),
        "ara_branslar": list(db.scalars(select(models.AraBrans).order_by(models.AraBrans.ad))),
        "subeler": list(db.scalars(select(models.Sube).where(models.Sube.aktif.is_(True)).order_by(models.Sube.ad))),
        "taliler": list(db.scalars(select(models.TaliAcente).where(models.TaliAcente.aktif.is_(True)).order_by(models.TaliAcente.ad))),
        "kullanicilar": list(db.scalars(select(models.Kullanici).where(models.Kullanici.aktif.is_(True)).order_by(models.Kullanici.ad_soyad))),
    }


def bul(db: Session, model, id_: int, ad: str = "Kayıt"):
    nesne = db.get(model, id_)
    if nesne is None:
        raise HTTPException(status_code=404, detail=f"{ad} bulunamadı")
    return nesne


def sayfala(db: Session, sorgu, sayfa: int, boy: int = SAYFA_BOYU) -> dict:
    from sqlalchemy import func
    sayfa = max(1, sayfa)
    toplam = db.scalar(select(func.count()).select_from(sorgu.order_by(None).subquery())) or 0
    kayitlar = list(db.scalars(sorgu.offset((sayfa - 1) * boy).limit(boy)))
    return {"kayitlar": kayitlar, "toplam": toplam, "sayfa": sayfa, "sayfa_sayisi": max(1, -(-toplam // boy)), "boy": boy}


def parametre(db: Session, ad: str, varsayilan: str = "") -> str:
    p = db.get(models.Parametre, ad)
    return p.deger if p and p.deger is not None else varsayilan


def bos(v: Optional[str]) -> Optional[str]:
    v = (v or "").strip()
    return v or None
