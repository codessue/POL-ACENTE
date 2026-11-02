"""JSON API (/api/v1). Oturum çerezi ile çalışır; mobil/entegrasyon için başlangıç noktası.
Belgeler: /api/docs
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli
from ..database import get_db
from ..services import yenileme_servisi

router = APIRouter(prefix="/api/v1", tags=["api"])


def _hesap(h: models.Hesap) -> dict:
    return {"id": h.id, "hes_kod": h.hes_kod, "unvan": h.unvan, "tip": h.tip, "tc_no": h.tc_no, "vergi_no": h.vergi_no, "gsm": h.gsm,
            "eposta": h.eposta, "il": h.il, "ilce": h.ilce, "temsilci": h.temsilci.ad_soyad if h.temsilci else None, "kvkk_onay": h.kvkk_onay}


def _police(p: models.Police) -> dict:
    return {"id": p.id, "police_no": p.police_no, "zeyl_no": p.zeyl_no, "yenileme_no": p.yenileme_no, "sirket": p.sirket.ad, "brans": p.ana_brans.ad,
            "hesap_id": p.hesap_id, "sigortali": p.hesap.unvan, "plaka": p.plaka, "tanzim": p.tanzim_tarihi.isoformat(), "baslama": p.baslama_tarihi.isoformat(),
            "bitis": p.bitis_tarihi.isoformat(), "brut_prim": float(p.brut_prim or 0), "net_prim": float(p.net_prim or 0), "komisyon": float(p.komisyon or 0),
            "durum": p.durum, "kalan_gun": p.kalan_gun}


@router.get("/hesaplar")
def hesaplar(q: str = "", limit: int = 20, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    H = models.Hesap
    s = select(H).where(H.aktif.is_(True))
    if q:
        like = f"%{q}%"
        tel = select(models.HesapTelefon.hesap_id).where(models.HesapTelefon.numara.like(like))
        s = s.where(or_(H.unvan.like(like), H.hes_kod.like(like), H.tc_no.like(like), H.vergi_no.like(like), H.id.in_(tel)))
    return [_hesap(h) for h in db.scalars(s.order_by(H.unvan).limit(min(limit, 100)))]


@router.get("/hesaplar/{hid}")
def hesap(hid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = db.get(models.Hesap, hid)
    if h is None:
        raise HTTPException(404, "Hesap bulunamadı")
    d = _hesap(h)
    d["policeler"] = [_police(p) for p in h.policeler]
    d["araclar"] = [{"id": a.id, "plaka": a.plaka, "marka": a.marka, "model": a.model, "model_yili": a.model_yili} for a in h.araclar]
    return d


@router.get("/policeler")
def policeler(q: str = "", durum: str = "", bitis_gun: Optional[int] = None, limit: int = 50, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    P = models.Police
    s = select(P)
    if q:
        like = f"%{q}%"
        s = s.where(or_(P.police_no.like(like), P.plaka.like(like.upper())))
    if durum:
        s = s.where(P.durum == durum)
    if bitis_gun is not None:
        s = s.where(P.durum == "Aktif", P.bitis_tarihi.between(date.today(), date.today() + timedelta(days=bitis_gun)))
    return [_police(p) for p in db.scalars(s.order_by(P.bitis_tarihi).limit(min(limit, 500)))]


@router.get("/policeler/{pid}")
def police(pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = db.get(models.Police, pid)
    if p is None:
        raise HTTPException(404, "Poliçe bulunamadı")
    d = _police(p)
    d["taksitler"] = [{"sira": t.sira, "vade": t.vade.isoformat(), "tutar": float(t.tutar), "odendi": t.odendi} for t in p.taksitler]
    return d


@router.get("/yenileme/ozet")
def yenileme_ozet(donem: Optional[str] = None, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    return yenileme_servisi.ozet(db, donem)


@router.get("/tanimlar")
def tanimlar(k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    return {
        "sirketler": [{"id": s.id, "kod": s.kod, "ad": s.ad} for s in db.scalars(select(models.SigortaSirketi).where(models.SigortaSirketi.aktif.is_(True)))],
        "branslar": [{"id": b.id, "kod": b.kod, "ad": b.ad} for b in db.scalars(select(models.AnaBrans))],
        "temsilciler": [{"id": t.id, "kod": t.kod, "ad": t.ad_soyad} for t in db.scalars(select(models.Temsilci).where(models.Temsilci.aktif.is_(True)))],
    }
