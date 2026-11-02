from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli
from ..database import get_db
from ..services import yenileme_servisi
from ..templating import render
from ..utils import donem

router = APIRouter(tags=["dashboard"])


@router.get("/")
def dashboard(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    bugun = date.today()
    ay_bas = bugun.replace(day=1)
    P = models.Police

    def sayi(q):
        return db.scalar(q) or 0

    kartlar = {
        "aktif_police": sayi(select(func.count(P.id)).where(P.durum == "Aktif")),
        "musteri": sayi(select(func.count(models.Hesap.id)).where(models.Hesap.aktif.is_(True))),
        "bu_ay_uretim": sayi(select(func.coalesce(func.sum(P.brut_prim), 0)).where(P.tanzim_tarihi >= ay_bas, P.durum != "İptal")),
        "bu_ay_adet": sayi(select(func.count(P.id)).where(P.tanzim_tarihi >= ay_bas, P.durum != "İptal")),
        "bu_ay_komisyon": sayi(select(func.coalesce(func.sum(P.komisyon), 0)).where(P.tanzim_tarihi >= ay_bas, P.durum != "İptal")),
        "bitecek_30": sayi(select(func.count(P.id)).where(P.durum == "Aktif", P.bitis_tarihi.between(bugun, bugun + timedelta(days=30)))),
        "bitecek_7": sayi(select(func.count(P.id)).where(P.durum == "Aktif", P.bitis_tarihi.between(bugun, bugun + timedelta(days=7)))),
        "gecikmis_taksit": sayi(select(func.coalesce(func.sum(models.Taksit.tutar), 0)).join(P).where(models.Taksit.odendi.is_(False), models.Taksit.vade < bugun, P.durum == "Aktif")),
        "acik_talep": sayi(select(func.count(models.Talep.id)).where(models.Talep.durum != "Kapandı")),
        "acik_potansiyel": sayi(select(func.count(models.Potansiyel.id)).where(models.Potansiyel.durum == "Açık")),
    }
    # bugünkü görevler
    gorevler = list(db.scalars(select(models.Gorev).where(models.Gorev.durum == "Açık", models.Gorev.tarih <= bugun)
                               .order_by(models.Gorev.tarih, models.Gorev.saat).limit(10)))
    # yaklaşan bitişler
    yaklasan = list(db.scalars(select(P).where(P.durum == "Aktif", P.bitis_tarihi.between(bugun - timedelta(days=3), bugun + timedelta(days=30)))
                               .order_by(P.bitis_tarihi).limit(15)))
    # yenileme özeti (bu dönem)
    yen = yenileme_servisi.ozet(db, donem(bugun))
    # branş bazlı üretim (son 12 ay)
    yil_once = bugun - timedelta(days=365)
    brans_uretim = db.execute(select(models.AnaBrans.ad, func.count(P.id), func.coalesce(func.sum(P.brut_prim), 0))
                              .join(P, P.ana_brans_id == models.AnaBrans.id).where(P.tanzim_tarihi >= yil_once, P.durum != "İptal")
                              .group_by(models.AnaBrans.ad).order_by(func.sum(P.brut_prim).desc())).all()
    sirket_uretim = db.execute(select(models.SigortaSirketi.ad, func.count(P.id), func.coalesce(func.sum(P.brut_prim), 0))
                               .join(P, P.sirket_id == models.SigortaSirketi.id).where(P.tanzim_tarihi >= yil_once, P.durum != "İptal")
                               .group_by(models.SigortaSirketi.ad).order_by(func.sum(P.brut_prim).desc()).limit(8)).all()
    # aylık üretim trendi (son 6 ay)
    aylar = []
    for i in range(5, -1, -1):
        ay = (ay_bas - timedelta(days=1)).replace(day=1) if i else ay_bas
        # geri git i ay
        y, m = ay_bas.year, ay_bas.month - i
        while m <= 0:
            m += 12
            y -= 1
        bas = date(y, m, 1)
        son = date(y + (m == 12), (m % 12) + 1, 1)
        top = sayi(select(func.coalesce(func.sum(P.brut_prim), 0)).where(P.tanzim_tarihi >= bas, P.tanzim_tarihi < son, P.durum != "İptal"))
        aylar.append((f"{m:02d}/{y}", float(top)))
    maks = max([a[1] for a in aylar] + [1])
    son_loglar = list(db.scalars(select(models.IslemLog).order_by(models.IslemLog.id.desc()).limit(8)))
    return render(request, "dashboard.html", kartlar=kartlar, gorevler=gorevler, yaklasan=yaklasan, yen=yen,
                  brans_uretim=brans_uretim, sirket_uretim=sirket_uretim, aylar=aylar, maks=maks, son_loglar=son_loglar,
                  donem_kodu=donem(bugun))
