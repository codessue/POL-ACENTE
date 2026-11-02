"""İlk kurulum: zorunlu tanımlar + isteğe bağlı demo verisi."""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .auth import sifre_ozetle

BRANSLAR = [
    ("TRF", "Trafik", True), ("KSK", "Kasko", True), ("KNT", "Konut", False), ("DSK", "DASK", False),
    ("SGL", "Sağlık", False), ("TSS", "Tamamlayıcı Sağlık", False), ("FKZ", "Ferdi Kaza", False),
    ("ISY", "İşyeri", False), ("NKL", "Nakliyat", False), ("HYT", "Hayat", False), ("SYH", "Seyahat Sağlık", False),
    ("SRM", "Sorumluluk", False), ("MHN", "Mühendislik", False),
]
ARA_BRANSLAR = {
    "TRF": ["Hususi Oto", "Kamyonet", "Motosiklet", "Ticari Taksi", "Otobüs"],
    "KSK": ["Genişletilmiş Kasko", "Dar Kasko", "Tam Kasko"],
    "KNT": ["Yangın", "Paket Konut", "Eşya"],
    "SGL": ["Yatarak Tedavi", "Yatarak + Ayakta"],
}
SIRKETLER = [("ANA", "Anadolu Sigorta"), ("AXA", "AXA Sigorta"), ("ALZ", "Allianz Sigorta"), ("AKS", "Aksigorta"),
             ("MPF", "Mapfre Sigorta"), ("HDI", "HDI Sigorta"), ("SMP", "Sompo Sigorta"), ("RAY", "Ray Sigorta"),
             ("TRK", "Türkiye Sigorta"), ("QCK", "Quick Sigorta")]
SABLONLAR = [
    ("Yenileme Hatırlatma (SMS)", "SMS", "", "Sayın {unvan}, {sirket} {brans} poliçeniz ({police_no}) {bitis} tarihinde sona eriyor. Yenileme teklifi için bizi arayın. {acente}"),
    ("Yenileme Hatırlatma (E-Posta)", "E-Posta", "{brans} poliçeniz {bitis} tarihinde sona eriyor",
     "Sayın {unvan},\n\n{sirket} şirketindeki {police_no} numaralı {brans} poliçeniz {bitis} tarihinde sona erecektir.\nYenileme teklifinizi hazırladık; dilediğiniz zaman bize ulaşabilirsiniz.\n\nSaygılarımızla,\n{acente}"),
    ("Doğum Günü", "SMS", "", "Sayın {unvan}, doğum gününüzü kutlar, sağlıklı ve mutlu bir yıl dileriz. {acente}"),
    ("Tahsilat Hatırlatma", "SMS", "", "Sayın {unvan}, {police_no} numaralı poliçenize ait {brut} TL ödemeniz beklenmektedir. Bilgi için bizi arayabilirsiniz. {acente}"),
    ("KVKK Bilgilendirme", "SMS", "", "Sayın {unvan}, kişisel verileriniz 6698 sayılı KVKK kapsamında sigorta işlemleriniz için işlenmektedir. Aydınlatma metni: {acente}"),
]

ADLAR = ["Ahmet", "Mehmet", "Ayşe", "Fatma", "Mustafa", "Zeynep", "Ali", "Elif", "Hüseyin", "Emine", "Hasan", "Hatice",
         "İbrahim", "Merve", "Yusuf", "Selin", "Ömer", "Esra", "Murat", "Büşra", "Kemal", "Derya", "Serkan", "Gamze"]
SOYADLAR = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım", "Öztürk", "Aydın", "Özdemir", "Arslan",
            "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek"]
FIRMALAR = ["Yıldız İnşaat Ltd. Şti.", "Akdeniz Gıda San. A.Ş.", "Mavi Lojistik Ltd. Şti.", "Güneş Tekstil A.Ş.",
            "Anadolu Nakliyat Ltd. Şti.", "Beyaz Eşya Pazarlama A.Ş."]
ILLER = [("İstanbul", "Kadıköy"), ("İstanbul", "Beşiktaş"), ("Ankara", "Çankaya"), ("İzmir", "Bornova"),
         ("Bursa", "Nilüfer"), ("Antalya", "Muratpaşa"), ("Kocaeli", "İzmit"), ("Konya", "Selçuklu")]
MARKALAR = [("Renault", "Clio"), ("Fiat", "Egea"), ("Toyota", "Corolla"), ("Volkswagen", "Polo"), ("Ford", "Focus"),
            ("Hyundai", "i20"), ("Honda", "Civic"), ("Peugeot", "208"), ("Dacia", "Duster"), ("Opel", "Astra")]


def ilk_kurulum(db: Session, demo: bool = False) -> None:
    if db.scalar(select(models.Kullanici.id)) is not None:
        return  # kurulum daha önce yapılmış
    sube = models.Sube(kod="MRK", ad="Merkez")
    db.add(sube)
    db.flush()
    temsilciler = [models.Temsilci(kod="T01", ad_soyad="Acente Yöneticisi", sube_id=sube.id)]
    if demo:
        temsilciler += [models.Temsilci(kod="T02", ad_soyad="Canan Ersoy", sube_id=sube.id, telefon="0532 000 00 02"),
                        models.Temsilci(kod="T03", ad_soyad="Burak Tekin", sube_id=sube.id, telefon="0532 000 00 03")]
    db.add_all(temsilciler)
    db.flush()
    db.add(models.Kullanici(kullanici_adi="admin", ad_soyad="Sistem Yöneticisi", sifre_hash=sifre_ozetle("admin"),
                            rol="admin", temsilci_id=temsilciler[0].id))
    for i, (kod, ad, arac) in enumerate(BRANSLAR):
        b = models.AnaBrans(kod=kod, ad=ad, arac_gerekli=arac, sira=i)
        for ara in ARA_BRANSLAR.get(kod, []):
            b.ara_branslar.append(models.AraBrans(ad=ara))
        db.add(b)
    for kod, ad in SIRKETLER:
        db.add(models.SigortaSirketi(kod=kod, ad=ad))
    for ad, kanal, konu, icerik in SABLONLAR:
        db.add(models.MesajSablon(ad=ad, kanal=kanal, konu=konu, icerik=icerik))
    db.add_all([
        models.Parametre(ad="acente_unvan", deger="Örnek Sigorta Aracılık Hizmetleri Ltd. Şti.", aciklama="Çıktılarda görünen acente ünvanı"),
        models.Parametre(ad="acente_telefon", deger="0212 000 00 00", aciklama="Acente telefonu"),
        models.Parametre(ad="varsayilan_komisyon_orani", deger="15", aciklama="Teklif girişinde net primden komisyon hesaplamak için %"),
    ])
    db.flush()
    sablon = db.scalar(select(models.MesajSablon).where(models.MesajSablon.ad.like("Yenileme Hatırlatma (SMS)%")))
    db.add(models.HatirlatmaKurali(ad="Bitişe 30 gün kala SMS", gun_once=30, kanal="SMS", sablon_id=sablon.id))
    db.commit()
    if demo:
        demo_verisi(db)


def demo_verisi(db: Session) -> None:
    rnd = random.Random(42)
    temsilciler = list(db.scalars(select(models.Temsilci)))
    sirketler = list(db.scalars(select(models.SigortaSirketi)))
    branslar = {b.kod: b for b in db.scalars(select(models.AnaBrans))}
    sube = db.scalar(select(models.Sube))
    bugun = date.today()
    hesaplar: list[models.Hesap] = []
    for i in range(40):
        kurumsal = i % 7 == 0
        il, ilce = rnd.choice(ILLER)
        if kurumsal:
            h = models.Hesap(hes_kod=f"H{i + 1:06d}", tip="Kurumsal", unvan=FIRMALAR[i % len(FIRMALAR)],
                             vergi_no=str(rnd.randint(1000000000, 9999999999)), vergi_dairesi=f"{ilce} VD")
            h.yetkililer.append(models.HesapYetkili(ad_soyad=f"{rnd.choice(ADLAR)} {rnd.choice(SOYADLAR)}", gorev="Muhasebe Müdürü",
                                                    telefon=f"05{rnd.randint(30, 55)} {rnd.randint(100, 999)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}"))
        else:
            ad, soyad = rnd.choice(ADLAR), rnd.choice(SOYADLAR)
            h = models.Hesap(hes_kod=f"H{i + 1:06d}", tip="Bireysel", unvan=f"{ad} {soyad}",
                             tc_no=str(rnd.randint(10000000000, 99999999999)),
                             dogum_tarihi=date(rnd.randint(1960, 2000), rnd.randint(1, 12), rnd.randint(1, 28)),
                             cinsiyet=rnd.choice(["Kadın", "Erkek"]), meslek=rnd.choice(["Öğretmen", "Mühendis", "Esnaf", "Doktor", "Memur", "Serbest"]))
        h.il, h.ilce, h.adres = il, ilce, f"{rnd.choice(['Atatürk', 'Cumhuriyet', 'İnönü', 'Bağdat'])} Cad. No:{rnd.randint(1, 200)}"
        h.temsilci_id = rnd.choice(temsilciler).id
        h.sube_id = sube.id
        h.kvkk_onay = rnd.random() < 0.8
        h.kvkk_tarih = bugun - timedelta(days=rnd.randint(10, 400)) if h.kvkk_onay else None
        h.kvkk_kanal = "SMS" if h.kvkk_onay else None
        h.olusturan = "admin"
        h.telefonlar.append(models.HesapTelefon(tip="GSM", numara=f"05{rnd.randint(30, 55)} {rnd.randint(100, 999)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}"))
        h.epostalar.append(models.HesapEposta(adres=f"{h.hes_kod.lower()}@ornek.com"))
        if rnd.random() < 0.75:
            marka, model = rnd.choice(MARKALAR)
            h.araclar.append(models.Arac(plaka=f"{rnd.randint(1, 81):02d}{rnd.choice('ABCDEFGHJKLMNPRSTUVYZ')}{rnd.choice('ABCDEFGHJKLMNPRSTUVYZ')}{rnd.randint(100, 999)}",
                                         marka=marka, model=model, model_yili=rnd.randint(2012, 2025), kullanim_tarzi="Hususi Oto"))
        db.add(h)
        hesaplar.append(h)
    db.flush()

    pno = 100000
    for hi, h in enumerate(hesaplar):
        adet = rnd.randint(1, 3)
        for pi in range(adet):
            if h.araclar and rnd.random() < 0.6:
                brans = branslar[rnd.choice(["TRF", "KSK"])]
                arac = h.araclar[0]
            else:
                brans = branslar[rnd.choice(["KNT", "DSK", "SGL", "TSS", "FKZ", "ISY"])]
                arac = None
            # bitiş: -60 .. +365 gün arası dağıt; böylece hem yenileme havuzu hem de son aylarda tanzim edilmiş üretim görünür
            bitis = bugun + timedelta(days=rnd.randint(-60, 120) if rnd.random() < 0.55 else rnd.randint(120, 365))
            bu_ay = hi < 8 and pi == 0  # birkaç poliçe bu ay tanzim edilmiş olsun (dashboard "bu ay üretim")
            if bu_ay:
                bitis = bugun + timedelta(days=365 - rnd.randint(0, bugun.day - 1))
            bas = bitis - timedelta(days=365)
            tanzim = bas if bu_ay else bas - timedelta(days=rnd.randint(0, 5))
            brut = Decimal(rnd.randint(1500, 45000))
            net = (brut / Decimal("1.05")).quantize(Decimal("0.01"))
            kom = (net * Decimal("0.15")).quantize(Decimal("0.01"))
            pno += 1
            p = models.Police(hesap_id=h.id, sirket_id=rnd.choice(sirketler).id, ana_brans_id=brans.id,
                              ara_brans_id=brans.ara_branslar[0].id if brans.ara_branslar else None,
                              police_no=str(pno), tanzim_tarihi=tanzim,
                              baslama_tarihi=bas, bitis_tarihi=bitis, brut_prim=brut, net_prim=net, komisyon=kom,
                              taksit_sayisi=rnd.choice([1, 1, 3, 6, 9]), odeme_sekli=rnd.choice(["Peşin", "Kredi Kartı", "Havale"]),
                              temsilci_id=h.temsilci_id, sube_id=sube.id, arac_id=arac.id if arac else None,
                              plaka=arac.plaka if arac else None, riziko_adresi=None if arac else h.adres,
                              durum="Aktif" if bitis >= bugun else "Süresi Doldu", olusturan="admin", kaynak="Manuel")
            db.add(p)
            db.flush()
            # taksit planı
            for s in range(p.taksit_sayisi):
                p.taksitler.append(models.Taksit(sira=s + 1, vade=bas + timedelta(days=30 * s), tutar=(brut / p.taksit_sayisi).quantize(Decimal("0.01"))))
            # tahsilat: geçmiş vadeler çoğunlukla ödenmiş
            for t in p.taksitler:
                if t.vade <= bugun and rnd.random() < 0.8:
                    t.odendi, t.odeme_tarihi = True, t.vade + timedelta(days=rnd.randint(0, 5))
                    db.add(models.Tahsilat(police_id=p.id, hesap_id=h.id, tarih=t.odeme_tarihi, tutar=t.tutar,
                                           tahsilat_sekli=p.odeme_sekli if p.odeme_sekli != "Peşin" else "Nakit", kullanici="admin",
                                           aciklama=f"{t.sira}. taksit"))
    # potansiyel (dış poliçe) kayıtları
    for i in range(12):
        ad, soyad = rnd.choice(ADLAR), rnd.choice(SOYADLAR)
        marka, model = rnd.choice(MARKALAR)
        il, ilce = rnd.choice(ILLER)
        db.add(models.Potansiyel(unvan=f"{ad} {soyad}", tc_no=str(rnd.randint(10000000000, 99999999999)),
                                 gsm=f"05{rnd.randint(30, 55)} {rnd.randint(100, 999)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}",
                                 il=il, ilce=ilce, ana_brans_id=branslar[rnd.choice(["TRF", "KSK"])].id,
                                 eski_sirket=rnd.choice(sirketler).ad, eski_acente="Başka Acente", eski_police_no=str(rnd.randint(500000, 999999)),
                                 eski_bitis=bugun + timedelta(days=rnd.randint(5, 90)), eski_brut_prim=Decimal(rnd.randint(2000, 30000)),
                                 plaka=f"{rnd.randint(1, 81):02d}XY{rnd.randint(100, 999)}", marka=marka, model=model, model_yili=rnd.randint(2010, 2024),
                                 temsilci_id=rnd.choice(temsilciler).id, kaynak=rnd.choice(["Web Formu", "Çağrı", "İçe Aktarım"]), olusturan="admin"))
    # görev / talep / çağrı örnekleri
    admin = db.scalar(select(models.Kullanici))
    for i in range(8):
        h = rnd.choice(hesaplar)
        db.add(models.Gorev(baslik=rnd.choice(["Müşteriyi ara", "Teklif gönder", "Ruhsat fotokopisi al", "Ziyaret"]),
                            tip=rnd.choice(["Görev", "Arama", "Randevu", "Ziyaret"]), tarih=bugun + timedelta(days=rnd.randint(-3, 10)),
                            saat=f"{rnd.randint(9, 17):02d}:00", hesap_id=h.id, atanan_id=admin.id, olusturan="admin"))
    for i in range(5):
        h = rnd.choice(hesaplar)
        p = h.policeler[0] if h.policeler else None
        t = models.Talep(hesap_id=h.id, police_id=p.id if p else None, talep_turu=rnd.choice(["Hasar", "Zeyil", "Bilgi", "Ödeme"]),
                         aciklama=rnd.choice(["Hasar dosyası açılması isteniyor.", "Adres değişikliği zeyili.", "Poliçe kopyası talep edildi.", "Taksit tarihini değiştirmek istiyor."]),
                         temsilci_id=h.temsilci_id, olusturan="admin")
        t.hareketler.append(models.TalepHareket(kullanici="admin", durum="Açık", aciklama="Talep açıldı"))
        db.add(t)
    for i in range(6):
        h = rnd.choice(hesaplar)
        db.add(models.Cagri(hesap_id=h.id, yon=rnd.choice(["Gelen", "Giden"]), telefon=h.gsm, neden=rnd.choice(["Yenileme", "Hasar", "Bilgi", "Tahsilat"]),
                            sonuc="Görüşüldü", sure_sn=rnd.randint(30, 400), kullanici="admin"))
    db.add(models.IslemLog(kullanici="sistem", islem="Demo verisi oluşturuldu", yer="sistem"))
    db.commit()
    # bitişi yaklaşanları sürece al
    from .services.yenileme_servisi import surece_al
    surece_al(db, 45)
    db.commit()
