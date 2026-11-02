"""Raporlar: üretim, yenileme, komisyon, tahsilat, temsilci performansı."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli
from ..database import get_db
from ..services import disa_aktar
from ..templating import render
from ..utils import tarih

router = APIRouter(prefix="/raporlar", tags=["raporlar"])
RAPORLAR = [
    ("uretim-sirket", "Şirket Bazlı Üretim"), ("uretim-brans", "Branş Bazlı Üretim"), ("uretim-temsilci", "Temsilci Performansı"),
    ("uretim-ay", "Aylık Üretim Trendi"), ("yenileme", "Yenileme Oranları"), ("tahsilat", "Tahsilat Durumu"), ("iptal", "İptal Poliçeler"),
    ("kayip", "Kaybedilen Müşteriler"),
]


def _aralik(request: Request):
    bugun = date.today()
    t1 = tarih(request.query_params.get("t1")) or bugun.replace(month=1, day=1)
    t2 = tarih(request.query_params.get("t2")) or bugun
    return t1, t2


def _rapor(db: Session, kod: str, t1: date, t2: date):
    P = models.Police
    temel = [P.tanzim_tarihi.between(t1, t2), P.durum != "İptal"]
    if kod == "uretim-sirket":
        kolon = ["Şirket", "Adet", "Brüt Prim", "Net Prim", "Komisyon", "Ort. Prim"]
        q = select(models.SigortaSirketi.ad, func.count(P.id), func.sum(P.brut_prim), func.sum(P.net_prim), func.sum(P.komisyon), func.avg(P.brut_prim)) \
            .join(P, P.sirket_id == models.SigortaSirketi.id).where(*temel).group_by(models.SigortaSirketi.ad).order_by(func.sum(P.brut_prim).desc())
    elif kod == "uretim-brans":
        kolon = ["Branş", "Adet", "Brüt Prim", "Net Prim", "Komisyon", "Ort. Prim"]
        q = select(models.AnaBrans.ad, func.count(P.id), func.sum(P.brut_prim), func.sum(P.net_prim), func.sum(P.komisyon), func.avg(P.brut_prim)) \
            .join(P, P.ana_brans_id == models.AnaBrans.id).where(*temel).group_by(models.AnaBrans.ad).order_by(func.sum(P.brut_prim).desc())
    elif kod == "uretim-temsilci":
        kolon = ["Temsilci", "Adet", "Brüt Prim", "Net Prim", "Komisyon", "Yeni İş", "Yenileme"]
        q = select(models.Temsilci.ad_soyad, func.count(P.id), func.sum(P.brut_prim), func.sum(P.net_prim), func.sum(P.komisyon),
                   func.sum(case((P.kaynak != "Yenileme", 1), else_=0)), func.sum(case((P.kaynak == "Yenileme", 1), else_=0))) \
            .join(P, P.temsilci_id == models.Temsilci.id).where(*temel).group_by(models.Temsilci.ad_soyad).order_by(func.sum(P.brut_prim).desc())
    elif kod == "uretim-ay":
        kolon = ["Ay", "Adet", "Brüt Prim", "Net Prim", "Komisyon"]
        ay = func.substr(cast(P.tanzim_tarihi, String), 1, 7)
        q = select(ay, func.count(P.id), func.sum(P.brut_prim), func.sum(P.net_prim), func.sum(P.komisyon)).where(*temel).group_by(ay).order_by(ay)
    elif kod == "yenileme":
        S = models.YenilemeSureci
        kolon = ["Dönem", "Toplam", "Yenilendi", "Kaybedildi", "Açık", "Yenileme %"]
        q = select(S.donem, func.count(S.id), func.sum(case((S.pozisyon == "Yenilendi", 1), else_=0)), func.sum(case((S.pozisyon == "Kaybedildi", 1), else_=0)),
                   func.sum(case((S.pozisyon.in_(models.ACIK_POZISYONLAR), 1), else_=0))).where(S.bitis_tarihi.between(t1, t2)).group_by(S.donem).order_by(S.donem)
        satir = []
        for d, top, yen, kay, acik in db.execute(q):
            kapanan = (yen or 0) + (kay or 0)
            satir.append((d, top, yen, kay, acik, round(100 * (yen or 0) / kapanan, 1) if kapanan else 0))
        return kolon, satir
    elif kod == "tahsilat":
        T = models.Taksit
        bugun = date.today()
        kolon = ["Şirket", "Toplam Taksit", "Ödenen", "Vadesi Geçmiş", "Vadesi Gelmemiş", "Ödenen Tutar", "Geciken Tutar"]
        q = select(models.SigortaSirketi.ad, func.count(T.id), func.sum(case((T.odendi.is_(True), 1), else_=0)),
                   func.sum(case(((T.odendi.is_(False)) & (T.vade < bugun), 1), else_=0)), func.sum(case(((T.odendi.is_(False)) & (T.vade >= bugun), 1), else_=0)),
                   func.sum(case((T.odendi.is_(True), T.tutar), else_=0)), func.sum(case(((T.odendi.is_(False)) & (T.vade < bugun), T.tutar), else_=0))) \
            .join(P, T.police_id == P.id).join(models.SigortaSirketi, P.sirket_id == models.SigortaSirketi.id) \
            .where(P.durum == "Aktif", P.tanzim_tarihi.between(t1, t2)).group_by(models.SigortaSirketi.ad)
    elif kod == "iptal":
        kolon = ["İptal Tarihi", "Poliçe No", "Şirket", "Branş", "Sigortalı", "Brüt Prim", "Neden"]
        satir = [(p.iptal_tarihi, p.police_no, p.sirket.ad, p.ana_brans.ad, p.hesap.unvan, p.brut_prim, p.iptal_nedeni or "")
                 for p in db.scalars(select(P).where(P.durum == "İptal", P.iptal_tarihi.between(t1, t2)).order_by(P.iptal_tarihi.desc()))]
        return kolon, satir
    elif kod == "kayip":
        S = models.YenilemeSureci
        kolon = ["Bitiş", "Sigortalı", "GSM", "Branş", "Eski Şirket", "Eski Prim", "Kayıp Nedeni", "Temsilci"]
        satir = [(s.bitis_tarihi, s.hesap.unvan, s.hesap.gsm, s.ana_brans.ad, s.police.sirket.ad if s.police else "-", s.police.brut_prim if s.police else 0,
                  s.sonuc_nedeni or "", s.temsilci.ad_soyad if s.temsilci else "")
                 for s in db.scalars(select(S).where(S.pozisyon == "Kaybedildi", S.bitis_tarihi.between(t1, t2)).order_by(S.bitis_tarihi.desc()))]
        return kolon, satir
    else:
        return [], []
    satir = [tuple((round(float(v), 2) if isinstance(v, (float, Decimal)) else v) for v in r) for r in db.execute(q)]
    return kolon, satir


@router.get("")
def ana(request: Request, k: models.Kullanici = Depends(giris_gerekli)):
    t1, t2 = _aralik(request)
    return render(request, "raporlar/liste.html", RAPORLAR=RAPORLAR, t1=t1, t2=t2)


@router.get("/{kod}")
def goster(request: Request, kod: str, bicim: str = "", k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    t1, t2 = _aralik(request)
    ad = dict(RAPORLAR).get(kod, kod)
    kolon, satir = _rapor(db, kod, t1, t2)
    if bicim == "xlsx":
        return Response(disa_aktar.excel_bytes(ad, kolon, satir), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename={kod}_{t1}_{t2}.xlsx"})
    if bicim == "csv":
        return Response(disa_aktar.csv_bytes(kolon, satir), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={kod}_{t1}_{t2}.csv"})
    toplamlar = []
    for i, _ in enumerate(kolon):
        try:
            toplamlar.append(sum(float(r[i]) for r in satir) if i > 0 and all(isinstance(r[i], (int, float, Decimal)) for r in satir) and satir else None)
        except Exception:
            toplamlar.append(None)
    return render(request, "raporlar/goster.html", RAPORLAR=RAPORLAR, kod=kod, ad=ad, kolon=kolon, satir=satir, toplamlar=toplamlar, t1=t1, t2=t2)
