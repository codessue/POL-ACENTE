"""Otomatik hatırlatma (PoliSoft 'alert' + 'Toplu Hatırlatma')."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from . import mesaj_servisi


def calistir(db: Session, kullanici: Optional[models.Kullanici] = None) -> int:
    """Aktif kuralları tarar, uygun poliçelere mesaj üretir. Gönderilen sayısını döner."""
    bugun = date.today()
    kadi = kullanici.kullanici_adi if kullanici else "zamanlayici"
    gonderilen = 0
    for kural in db.scalars(select(models.HatirlatmaKurali).where(models.HatirlatmaKurali.aktif.is_(True))):
        hedef = bugun + timedelta(days=kural.gun_once)
        q = select(models.Police).where(models.Police.durum == "Aktif", models.Police.bitis_tarihi <= hedef,
                                        models.Police.bitis_tarihi >= bugun)
        if kural.ana_brans_id:
            q = q.where(models.Police.ana_brans_id == kural.ana_brans_id)
        yapilmis = {r[0] for r in db.execute(select(models.HatirlatmaGonderim.police_id).where(models.HatirlatmaGonderim.kural_id == kural.id))}
        for p in db.scalars(q):
            if p.id in yapilmis:
                continue
            h = p.hesap
            if not h.kvkk_onay:
                continue  # KVKK onayı olmayan müşteriye otomatik ileti gitmez
            alici = h.eposta if kural.kanal == "E-Posta" else h.gsm
            if not alici:
                continue
            icerik = mesaj_servisi.sablon_doldur(kural.sablon.icerik, h, p)
            konu = mesaj_servisi.sablon_doldur(kural.sablon.konu or "", h, p)
            mesaj_servisi.gonder(db, kural.kanal, alici, icerik, konu, h, p, kadi)
            db.add(models.HatirlatmaGonderim(kural_id=kural.id, police_id=p.id))
            gonderilen += 1
    db.commit()
    return gonderilen
