"""Veri modeli.

PoliSoft'un MySQL şemasındaki ana kavramların (hesapkart, police, dispolice, pyshareket/pysteklif,
pbs_tahsilat, jobs, talep, cagri, iletidoc, userfiles, llpano, alert...) sadeleştirilmiş ve
Türkçe isimlendirilmiş açık kaynak karşılıkları.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, Index)
from sqlalchemy.orm import relationship

from .database import Base


def simdi() -> datetime:
    return datetime.now()


# --------------------------------------------------------------------------- tanımlar
class Kullanici(Base):
    __tablename__ = "kullanici"
    id = Column(Integer, primary_key=True)
    kullanici_adi = Column(String(50), unique=True, nullable=False)
    ad_soyad = Column(String(120), nullable=False)
    sifre_hash = Column(String(255), nullable=False)
    rol = Column(String(20), default="temsilci")  # admin | yonetici | temsilci
    eposta = Column(String(120))
    temsilci_id = Column(Integer, ForeignKey("temsilci.id"))
    aktif = Column(Boolean, default=True)
    olusturma = Column(DateTime, default=simdi)
    temsilci = relationship("Temsilci")


class Sube(Base):
    __tablename__ = "sube"
    id = Column(Integer, primary_key=True)
    kod = Column(String(20), unique=True)
    ad = Column(String(120), nullable=False)
    aktif = Column(Boolean, default=True)


class Temsilci(Base):
    __tablename__ = "temsilci"
    id = Column(Integer, primary_key=True)
    kod = Column(String(20), unique=True)
    ad_soyad = Column(String(120), nullable=False)
    sube_id = Column(Integer, ForeignKey("sube.id"))
    telefon = Column(String(30))
    eposta = Column(String(120))
    aktif = Column(Boolean, default=True)
    sube = relationship("Sube")


class SigortaSirketi(Base):
    __tablename__ = "sigorta_sirketi"
    id = Column(Integer, primary_key=True)
    kod = Column(String(20), unique=True)
    ad = Column(String(120), nullable=False)
    acente_kodu = Column(String(50))
    telefon = Column(String(30))
    web = Column(String(200))
    aktif = Column(Boolean, default=True)


class TaliAcente(Base):
    __tablename__ = "tali_acente"
    id = Column(Integer, primary_key=True)
    kod = Column(String(20), unique=True)
    ad = Column(String(120), nullable=False)
    komisyon_orani = Column(Numeric(5, 2), default=0)
    telefon = Column(String(30))
    aktif = Column(Boolean, default=True)


class AnaBrans(Base):
    __tablename__ = "ana_brans"
    id = Column(Integer, primary_key=True)
    kod = Column(String(20), unique=True, nullable=False)
    ad = Column(String(80), nullable=False)
    arac_gerekli = Column(Boolean, default=False)  # Trafik/Kasko için plaka zorunlu
    sira = Column(Integer, default=0)
    ara_branslar = relationship("AraBrans", back_populates="ana_brans", cascade="all, delete-orphan")


class AraBrans(Base):
    __tablename__ = "ara_brans"
    id = Column(Integer, primary_key=True)
    ana_brans_id = Column(Integer, ForeignKey("ana_brans.id"), nullable=False)
    kod = Column(String(20))
    ad = Column(String(120), nullable=False)
    ana_brans = relationship("AnaBrans", back_populates="ara_branslar")


class Parametre(Base):
    __tablename__ = "parametre"
    ad = Column(String(80), primary_key=True)
    deger = Column(Text)
    aciklama = Column(String(255))


# --------------------------------------------------------------------------- hesap kartı
class Hesap(Base):
    """PoliSoft 'hesapkart' karşılığı: müşteri/sigortalı kartı."""
    __tablename__ = "hesap"
    id = Column(Integer, primary_key=True)
    hes_kod = Column(String(30), unique=True, nullable=False)
    tip = Column(String(20), default="Bireysel")  # Bireysel | Kurumsal
    unvan = Column(String(200), nullable=False)
    tc_no = Column(String(11), index=True)
    vergi_no = Column(String(11), index=True)
    vergi_dairesi = Column(String(80))
    dogum_tarihi = Column(Date)
    cinsiyet = Column(String(10))
    meslek = Column(String(80))
    il = Column(String(40))
    ilce = Column(String(40))
    adres = Column(String(400))
    grup = Column(String(80))
    referans = Column(String(80))
    temsilci_id = Column(Integer, ForeignKey("temsilci.id"))
    sube_id = Column(Integer, ForeignKey("sube.id"))
    tali_id = Column(Integer, ForeignKey("tali_acente.id"))
    kvkk_onay = Column(Boolean, default=False)
    kvkk_tarih = Column(Date)
    kvkk_kanal = Column(String(30))
    notlar = Column(Text)
    aktif = Column(Boolean, default=True)
    olusturma = Column(DateTime, default=simdi)
    olusturan = Column(String(50))

    temsilci = relationship("Temsilci")
    sube = relationship("Sube")
    tali = relationship("TaliAcente")
    telefonlar = relationship("HesapTelefon", back_populates="hesap", cascade="all, delete-orphan")
    epostalar = relationship("HesapEposta", back_populates="hesap", cascade="all, delete-orphan")
    yetkililer = relationship("HesapYetkili", back_populates="hesap", cascade="all, delete-orphan")
    araclar = relationship("Arac", back_populates="hesap", cascade="all, delete-orphan")
    policeler = relationship("Police", back_populates="hesap", order_by="Police.bitis_tarihi.desc()")

    @property
    def gsm(self):
        for t in self.telefonlar:
            if t.tip == "GSM":
                return t.numara
        return self.telefonlar[0].numara if self.telefonlar else ""

    @property
    def eposta(self):
        return self.epostalar[0].adres if self.epostalar else ""

    @property
    def kimlik_no(self):
        return self.tc_no or self.vergi_no or ""


class HesapTelefon(Base):
    __tablename__ = "hesap_telefon"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id", ondelete="CASCADE"), nullable=False)
    tip = Column(String(20), default="GSM")  # GSM | Ev | İş | Faks
    numara = Column(String(30), nullable=False, index=True)
    aciklama = Column(String(80))
    hesap = relationship("Hesap", back_populates="telefonlar")


class HesapEposta(Base):
    __tablename__ = "hesap_eposta"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id", ondelete="CASCADE"), nullable=False)
    adres = Column(String(150), nullable=False)
    tip = Column(String(20), default="Kişisel")
    hesap = relationship("Hesap", back_populates="epostalar")


class HesapYetkili(Base):
    __tablename__ = "hesap_yetkili"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id", ondelete="CASCADE"), nullable=False)
    ad_soyad = Column(String(120), nullable=False)
    gorev = Column(String(80))
    telefon = Column(String(30))
    eposta = Column(String(120))
    hesap = relationship("Hesap", back_populates="yetkililer")


class Arac(Base):
    __tablename__ = "arac"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id", ondelete="CASCADE"), nullable=False)
    plaka = Column(String(15), nullable=False, index=True)
    marka = Column(String(60))
    model = Column(String(80))
    model_yili = Column(Integer)
    kullanim_tarzi = Column(String(60))
    motor_no = Column(String(40))
    sasi_no = Column(String(40))
    tescil_tarihi = Column(Date)
    ruhsat_seri_no = Column(String(30))
    hesap = relationship("Hesap", back_populates="araclar")


# --------------------------------------------------------------------------- poliçe
class Police(Base):
    """PoliSoft 'police' karşılığı."""
    __tablename__ = "police"
    __table_args__ = (
        UniqueConstraint("sirket_id", "police_no", "zeyl_no", "yenileme_no", name="uq_police_anahtar"),
        Index("ix_police_bitis", "bitis_tarihi"),
    )
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id"), nullable=False)
    sirket_id = Column(Integer, ForeignKey("sigorta_sirketi.id"), nullable=False)
    ana_brans_id = Column(Integer, ForeignKey("ana_brans.id"), nullable=False)
    ara_brans_id = Column(Integer, ForeignKey("ara_brans.id"))
    police_no = Column(String(40), nullable=False)
    zeyl_no = Column(Integer, default=0)
    yenileme_no = Column(Integer, default=0)
    tanzim_tarihi = Column(Date, nullable=False)
    baslama_tarihi = Column(Date, nullable=False)
    bitis_tarihi = Column(Date, nullable=False)
    para_birimi = Column(String(3), default="TRY")
    brut_prim = Column(Numeric(14, 2), default=0)
    net_prim = Column(Numeric(14, 2), default=0)
    komisyon = Column(Numeric(14, 2), default=0)
    taksit_sayisi = Column(Integer, default=1)
    odeme_sekli = Column(String(30), default="Peşin")  # Peşin | Kredi Kartı | Havale | Senet
    temsilci_id = Column(Integer, ForeignKey("temsilci.id"))
    tali_id = Column(Integer, ForeignKey("tali_acente.id"))
    sube_id = Column(Integer, ForeignKey("sube.id"))
    arac_id = Column(Integer, ForeignKey("arac.id"))
    plaka = Column(String(15), index=True)
    riziko_adresi = Column(String(400))
    durum = Column(String(20), default="Aktif")  # Aktif | İptal | Yenilendi | Süresi Doldu
    iptal_tarihi = Column(Date)
    iptal_nedeni = Column(String(200))
    onceki_police_id = Column(Integer, ForeignKey("police.id"))
    kaynak = Column(String(30), default="Manuel")  # Manuel | İçe Aktarım | Yenileme | Potansiyel
    aciklama = Column(Text)
    olusturma = Column(DateTime, default=simdi)
    olusturan = Column(String(50))

    hesap = relationship("Hesap", back_populates="policeler")
    sirket = relationship("SigortaSirketi")
    ana_brans = relationship("AnaBrans")
    ara_brans = relationship("AraBrans")
    temsilci = relationship("Temsilci")
    tali = relationship("TaliAcente")
    sube = relationship("Sube")
    arac = relationship("Arac")
    taksitler = relationship("Taksit", back_populates="police", cascade="all, delete-orphan", order_by="Taksit.sira")
    tahsilatlar = relationship("Tahsilat", back_populates="police")

    @property
    def kalan_gun(self) -> int:
        return (self.bitis_tarihi - date.today()).days if self.bitis_tarihi else 0

    @property
    def tahsil_edilen(self) -> Decimal:
        return sum((Decimal(str(t.tutar)) for t in self.tahsilatlar if t.durum == "Tahsil Edildi"), Decimal("0"))

    @property
    def bakiye(self) -> Decimal:
        return Decimal(str(self.brut_prim or 0)) - self.tahsil_edilen


class Taksit(Base):
    __tablename__ = "taksit"
    id = Column(Integer, primary_key=True)
    police_id = Column(Integer, ForeignKey("police.id", ondelete="CASCADE"), nullable=False)
    sira = Column(Integer, nullable=False)
    vade = Column(Date, nullable=False)
    tutar = Column(Numeric(14, 2), nullable=False)
    odendi = Column(Boolean, default=False)
    odeme_tarihi = Column(Date)
    police = relationship("Police", back_populates="taksitler")


class Tahsilat(Base):
    """PoliSoft 'pbs_tahsilat' karşılığı."""
    __tablename__ = "tahsilat"
    id = Column(Integer, primary_key=True)
    police_id = Column(Integer, ForeignKey("police.id"), nullable=False)
    hesap_id = Column(Integer, ForeignKey("hesap.id"), nullable=False)
    tarih = Column(Date, nullable=False, default=date.today)
    tutar = Column(Numeric(14, 2), nullable=False)
    tahsilat_sekli = Column(String(30), default="Nakit")  # Nakit | Kredi Kartı | Havale/EFT | Çek | Senet
    durum = Column(String(20), default="Tahsil Edildi")  # Tahsil Edildi | Bekliyor | İade
    makbuz_no = Column(String(40))
    aciklama = Column(String(300))
    kullanici = Column(String(50))
    olusturma = Column(DateTime, default=simdi)
    police = relationship("Police", back_populates="tahsilatlar")
    hesap = relationship("Hesap")


# --------------------------------------------------------------------------- yenileme süreci & teklif
YENILEME_POZISYONLARI = ["Bekliyor", "Arandı", "Teklif Alındı", "Teklif Sunuldu", "Yenilendi", "Kaybedildi", "İptal"]
ACIK_POZISYONLAR = YENILEME_POZISYONLARI[:4]


class YenilemeSureci(Base):
    """PoliSoft 'pyshareket' / 'pysgrup' karşılığı: bitişi yaklaşan poliçe veya potansiyel için takip kaydı."""
    __tablename__ = "yenileme_sureci"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id"), nullable=False)
    police_id = Column(Integer, ForeignKey("police.id"))
    potansiyel_id = Column(Integer, ForeignKey("potansiyel.id"))
    ana_brans_id = Column(Integer, ForeignKey("ana_brans.id"), nullable=False)
    donem = Column(String(7), index=True)  # MM-YYYY
    bitis_tarihi = Column(Date, nullable=False)
    pozisyon = Column(String(30), default="Bekliyor", index=True)
    temsilci_id = Column(Integer, ForeignKey("temsilci.id"))
    sonuc_nedeni = Column(String(200))
    kapanis_tarihi = Column(Date)
    yeni_police_id = Column(Integer, ForeignKey("police.id"))
    olusturma = Column(DateTime, default=simdi)

    hesap = relationship("Hesap")
    police = relationship("Police", foreign_keys=[police_id])
    yeni_police = relationship("Police", foreign_keys=[yeni_police_id])
    potansiyel = relationship("Potansiyel")
    ana_brans = relationship("AnaBrans")
    temsilci = relationship("Temsilci")
    hareketler = relationship("YenilemeHareket", back_populates="surec", cascade="all, delete-orphan", order_by="YenilemeHareket.tarih.desc()")
    teklifler = relationship("Teklif", back_populates="surec", cascade="all, delete-orphan")

    @property
    def acik(self) -> bool:
        return self.pozisyon in ACIK_POZISYONLAR

    @property
    def kalan_gun(self) -> int:
        return (self.bitis_tarihi - date.today()).days


class YenilemeHareket(Base):
    __tablename__ = "yenileme_hareket"
    id = Column(Integer, primary_key=True)
    surec_id = Column(Integer, ForeignKey("yenileme_sureci.id", ondelete="CASCADE"), nullable=False)
    tarih = Column(DateTime, default=simdi)
    kullanici = Column(String(50))
    pozisyon = Column(String(30))
    aciklama = Column(String(500))
    surec = relationship("YenilemeSureci", back_populates="hareketler")


class Teklif(Base):
    """PoliSoft 'pysteklif' karşılığı: şirket bazlı teklif tutarları."""
    __tablename__ = "teklif"
    id = Column(Integer, primary_key=True)
    surec_id = Column(Integer, ForeignKey("yenileme_sureci.id", ondelete="CASCADE"), nullable=False)
    sirket_id = Column(Integer, ForeignKey("sigorta_sirketi.id"), nullable=False)
    teklif_no = Column(String(40))
    brut_prim = Column(Numeric(14, 2), default=0)
    net_prim = Column(Numeric(14, 2), default=0)
    komisyon = Column(Numeric(14, 2), default=0)
    odeme_tipi = Column(String(30), default="Peşin")
    taksit_sayisi = Column(Integer, default=1)
    tarih = Column(Date, default=date.today)
    secildi = Column(Boolean, default=False)
    aciklama = Column(String(300))
    kullanici = Column(String(50))
    surec = relationship("YenilemeSureci", back_populates="teklifler")
    sirket = relationship("SigortaSirketi")


class Potansiyel(Base):
    """PoliSoft 'dispolice' karşılığı: başka acentede/şirkette olan (dış) poliçe, çapraz satış adayı."""
    __tablename__ = "potansiyel"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id"))
    unvan = Column(String(200), nullable=False)
    tc_no = Column(String(11))
    vergi_no = Column(String(11))
    gsm = Column(String(30))
    telefon = Column(String(30))
    eposta = Column(String(120))
    il = Column(String(40))
    ilce = Column(String(40))
    adres = Column(String(400))
    ana_brans_id = Column(Integer, ForeignKey("ana_brans.id"), nullable=False)
    eski_sirket = Column(String(120))
    eski_acente = Column(String(120))
    eski_police_no = Column(String(40))
    eski_tanzim = Column(Date)
    eski_baslama = Column(Date)
    eski_bitis = Column(Date, index=True)
    eski_brut_prim = Column(Numeric(14, 2), default=0)
    plaka = Column(String(15))
    marka = Column(String(60))
    model = Column(String(80))
    model_yili = Column(Integer)
    temsilci_id = Column(Integer, ForeignKey("temsilci.id"))
    kaynak = Column(String(40), default="Manuel")  # Manuel | İçe Aktarım | Web Formu | Çağrı
    durum = Column(String(20), default="Açık")  # Açık | Sürece Alındı | Kazanıldı | Kaybedildi
    aciklama = Column(Text)
    olusturma = Column(DateTime, default=simdi)
    olusturan = Column(String(50))
    hesap = relationship("Hesap")
    ana_brans = relationship("AnaBrans")
    temsilci = relationship("Temsilci")


# --------------------------------------------------------------------------- ajanda / talep / çağrı
class Gorev(Base):
    """PoliSoft 'jobs' + 'randevu' karşılığı."""
    __tablename__ = "gorev"
    id = Column(Integer, primary_key=True)
    baslik = Column(String(200), nullable=False)
    aciklama = Column(Text)
    tip = Column(String(20), default="Görev")  # Görev | Randevu | Ziyaret | Hatırlatma | Arama
    tarih = Column(Date, nullable=False, default=date.today)
    saat = Column(String(5))
    hesap_id = Column(Integer, ForeignKey("hesap.id"))
    police_id = Column(Integer, ForeignKey("police.id"))
    atanan_id = Column(Integer, ForeignKey("kullanici.id"))
    olusturan = Column(String(50))
    durum = Column(String(20), default="Açık")  # Açık | Tamamlandı | İptal
    tamamlanma = Column(DateTime)
    sonuc = Column(String(500))
    olusturma = Column(DateTime, default=simdi)
    hesap = relationship("Hesap")
    police = relationship("Police")
    atanan = relationship("Kullanici")


class Talep(Base):
    __tablename__ = "talep"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id"), nullable=False)
    police_id = Column(Integer, ForeignKey("police.id"))
    talep_turu = Column(String(60), nullable=False)  # Hasar | Zeyil | İptal | Bilgi | Şikayet | Ödeme | Diğer
    aciklama = Column(Text, nullable=False)
    durum = Column(String(20), default="Açık")  # Açık | İşlemde | Kapandı
    durum_aciklama = Column(String(500))
    temsilci_id = Column(Integer, ForeignKey("temsilci.id"))
    olusturan = Column(String(50))
    olusturma = Column(DateTime, default=simdi)
    kapanis = Column(DateTime)
    hesap = relationship("Hesap")
    police = relationship("Police")
    temsilci = relationship("Temsilci")
    hareketler = relationship("TalepHareket", back_populates="talep", cascade="all, delete-orphan", order_by="TalepHareket.tarih.desc()")


class TalepHareket(Base):
    __tablename__ = "talep_hareket"
    id = Column(Integer, primary_key=True)
    talep_id = Column(Integer, ForeignKey("talep.id", ondelete="CASCADE"), nullable=False)
    tarih = Column(DateTime, default=simdi)
    kullanici = Column(String(50))
    durum = Column(String(20))
    aciklama = Column(String(500))
    talep = relationship("Talep", back_populates="hareketler")


class Cagri(Base):
    __tablename__ = "cagri"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id"))
    yon = Column(String(10), default="Giden")  # Gelen | Giden
    tarih = Column(DateTime, default=simdi)
    telefon = Column(String(30))
    neden = Column(String(80))
    sonuc = Column(String(500))
    sure_sn = Column(Integer, default=0)
    kullanici = Column(String(50))
    hesap = relationship("Hesap")


# --------------------------------------------------------------------------- mesajlaşma
class MesajSablon(Base):
    """SMS / e-posta şablonları. {unvan} {police_no} {bitis} {plaka} {brut} {sirket} {acente} {brans} değişkenleri desteklenir."""
    __tablename__ = "mesaj_sablon"
    id = Column(Integer, primary_key=True)
    ad = Column(String(80), nullable=False)
    kanal = Column(String(10), default="SMS")  # SMS | E-Posta | WhatsApp
    konu = Column(String(150))
    icerik = Column(Text, nullable=False)
    aktif = Column(Boolean, default=True)


class Mesaj(Base):
    """PoliSoft 'iletidoc' karşılığı: gönderilen her ileti burada loglanır."""
    __tablename__ = "mesaj"
    id = Column(Integer, primary_key=True)
    hesap_id = Column(Integer, ForeignKey("hesap.id"))
    police_id = Column(Integer, ForeignKey("police.id"))
    kanal = Column(String(10), nullable=False)
    alici = Column(String(150), nullable=False)
    konu = Column(String(150))
    icerik = Column(Text, nullable=False)
    durum = Column(String(20), default="Kuyrukta")  # Kuyrukta | Gönderildi | Hata
    hata = Column(String(300))
    tarih = Column(DateTime, default=simdi)
    kullanici = Column(String(50))
    hesap = relationship("Hesap")


class HatirlatmaKurali(Base):
    """PoliSoft 'alert' karşılığı: bitişine N gün kala otomatik mesaj."""
    __tablename__ = "hatirlatma_kurali"
    id = Column(Integer, primary_key=True)
    ad = Column(String(100), nullable=False)
    aktif = Column(Boolean, default=True)
    gun_once = Column(Integer, default=30)
    kanal = Column(String(10), default="SMS")
    sablon_id = Column(Integer, ForeignKey("mesaj_sablon.id"), nullable=False)
    ana_brans_id = Column(Integer, ForeignKey("ana_brans.id"))  # boş = tüm branşlar
    sablon = relationship("MesajSablon")
    ana_brans = relationship("AnaBrans")


class HatirlatmaGonderim(Base):
    """Aynı poliçeye aynı kural ile iki kez gitmesin diye."""
    __tablename__ = "hatirlatma_gonderim"
    __table_args__ = (UniqueConstraint("kural_id", "police_id", name="uq_kural_police"),)
    id = Column(Integer, primary_key=True)
    kural_id = Column(Integer, ForeignKey("hatirlatma_kurali.id", ondelete="CASCADE"))
    police_id = Column(Integer, ForeignKey("police.id", ondelete="CASCADE"))
    tarih = Column(DateTime, default=simdi)


# --------------------------------------------------------------------------- dosya & log
class Dosya(Base):
    """PoliSoft 'userfiles' karşılığı."""
    __tablename__ = "dosya"
    id = Column(Integer, primary_key=True)
    yer = Column(String(20), nullable=False, index=True)  # hesap | police | talep | potansiyel
    yer_id = Column(Integer, nullable=False, index=True)
    orijinal_ad = Column(String(255), nullable=False)
    sistem_ad = Column(String(80), nullable=False)
    boyut = Column(Integer, default=0)
    uzanti = Column(String(10))
    tur = Column(String(40))  # Poliçe | Ruhsat | Kimlik | Teklif | Hasar | Diğer
    aciklama = Column(String(255))
    kullanici = Column(String(50))
    tarih = Column(DateTime, default=simdi)


class IslemLog(Base):
    """PoliSoft 'llpano' / 'lltanimlog' karşılığı."""
    __tablename__ = "islem_log"
    id = Column(Integer, primary_key=True)
    tarih = Column(DateTime, default=simdi, index=True)
    kullanici = Column(String(50))
    islem = Column(String(80), nullable=False)
    yer = Column(String(30))
    yer_id = Column(Integer)
    aciklama = Column(String(1000))
