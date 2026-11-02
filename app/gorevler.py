"""Komut satırı görevleri (zamanlayıcı / cron ile çalıştırılır).

    python -m app.gorevler hatirlat      # hatırlatma kurallarını çalıştır
    python -m app.gorevler havuz [gün]   # bitişi yaklaşan poliçeleri yenileme sürecine al
    python -m app.gorevler suresi-dolan  # bitişi geçmiş aktif poliçeleri 'Süresi Doldu' yap
    python -m app.gorevler sifre-sifirla <kullanici> <yeni_sifre>
"""
import sys
from datetime import date

from sqlalchemy import select

from . import models
from .auth import sifre_ozetle
from .config import settings
from .database import Base, SessionLocal, engine
from .services import hatirlatma_servisi, yenileme_servisi


def main(argv: list[str]) -> int:
    Base.metadata.create_all(bind=engine)
    komut = argv[0] if argv else "yardim"
    with SessionLocal() as db:
        if komut == "hatirlat":
            print(f"{hatirlatma_servisi.calistir(db)} ileti üretildi")
        elif komut == "havuz":
            gun = int(argv[1]) if len(argv) > 1 else settings.YENILEME_GUN
            n = yenileme_servisi.surece_al(db, gun)
            db.commit()
            print(f"{n} poliçe sürece alındı")
        elif komut == "suresi-dolan":
            n = 0
            for p in db.scalars(select(models.Police).where(models.Police.durum == "Aktif", models.Police.bitis_tarihi < date.today())):
                p.durum = "Süresi Doldu"
                n += 1
            db.commit()
            print(f"{n} poliçe 'Süresi Doldu' olarak işaretlendi")
        elif komut == "sifre-sifirla" and len(argv) >= 3:
            k = db.scalar(select(models.Kullanici).where(models.Kullanici.kullanici_adi == argv[1]))
            if k is None:
                print("kullanıcı bulunamadı")
                return 1
            k.sifre_hash = sifre_ozetle(argv[2])
            db.commit()
            print("parola güncellendi")
        else:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
