"""Uçtan uca duman testleri: geçici SQLite veritabanı + demo verisi ile tüm ana sayfalar ve akışlar."""
import os
import tempfile
from datetime import date, timedelta

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db').replace(os.sep, '/')}"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["DEMO_VERI"] = "1"
os.environ["MESAJ_SAGLAYICI"] = "log"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        r = client.post("/login", data={"kullanici_adi": "admin", "sifre": "admin", "sonraki": "/"}, follow_redirects=False)
        assert r.status_code == 303
        yield client


def test_giris_zorunlu():
    with TestClient(app) as anon:
        r = anon.get("/", follow_redirects=False)
        assert r.status_code == 303 and "/login" in r.headers["location"]
        assert anon.get("/api/v1/hesaplar").status_code == 401


def test_hatali_giris():
    with TestClient(app) as anon:
        r = anon.post("/login", data={"kullanici_adi": "admin", "sifre": "yanlis"})
        assert r.status_code == 200 and "hatalı" in r.text


@pytest.mark.parametrize("yol", ["/", "/hesaplar", "/hesaplar?q=Yıl", "/policeler", "/policeler?on=30", "/yenileme", "/yenileme?gorunum=liste",
                                 "/potansiyel", "/tahsilat", "/tahsilat?gorunum=tahsilatlar", "/ajanda", "/ajanda?gorunum=ay", "/talepler", "/mesajlar",
                                 "/mesajlar/sablonlar", "/mesajlar/toplu", "/raporlar", "/raporlar/uretim-sirket", "/raporlar/uretim-brans",
                                 "/raporlar/uretim-temsilci", "/raporlar/uretim-ay", "/raporlar/yenileme", "/raporlar/tahsilat", "/raporlar/iptal",
                                 "/raporlar/kayip", "/tanimlar/sirketler", "/tanimlar/temsilciler", "/tanimlar/branslar", "/tanimlar/kullanicilar",
                                 "/tanimlar/parametreler", "/tanimlar/loglar", "/policeler/ice-aktar", "/policeler/yeni", "/hesaplar/yeni", "/potansiyel/yeni",
                                 "/ajanda/yeni", "/talepler/yeni", "/sifre", "/api/docs"])
def test_sayfalar_acilir(c, yol):
    r = c.get(yol)
    assert r.status_code == 200, f"{yol}: {r.status_code}"


def test_api(c):
    hesaplar = c.get("/api/v1/hesaplar?q=H0000").json()
    assert hesaplar and "unvan" in hesaplar[0]
    d = c.get(f"/api/v1/hesaplar/{hesaplar[0]['id']}").json()
    assert "policeler" in d
    assert isinstance(c.get("/api/v1/policeler?bitis_gun=30").json(), list)
    assert "oran" in c.get("/api/v1/yenileme/ozet").json()


def test_hesap_police_yenileme_akisi(c):
    # 1) hesap kartı
    r = c.post("/hesaplar/yeni", data={"hes_kod": "TEST001", "tip": "Bireysel", "unvan": "Test Müşteri", "tc_no": "12345678901", "gsm": "0532 111 22 33",
                                       "kvkk_onay": "1", "kvkk_kanal": "SMS"}, follow_redirects=False)
    assert r.status_code == 303
    hid = int(r.headers["location"].rsplit("/", 1)[1])
    assert "Test Müşteri" in c.get(f"/hesaplar/{hid}").text
    # geçersiz TC reddedilir
    r = c.post("/hesaplar/yeni", data={"unvan": "X", "tc_no": "123"})
    assert "11 haneli" in r.text
    # 2) araç
    c.post(f"/hesaplar/{hid}/arac", data={"plaka": "34 test 123", "marka": "Fiat", "model": "Egea"})
    assert "34TEST123" in c.get(f"/hesaplar/{hid}?sekme=araclar").text
    # 3) poliçe (trafik, plaka zorunlu)
    tan = c.get("/api/v1/tanimlar").json()
    sirket = tan["sirketler"][0]["id"]
    trf = next(b["id"] for b in tan["branslar"] if b["kod"] == "TRF")
    bugun = date.today()
    veri = {"hesap_id": hid, "sirket_id": sirket, "ana_brans_id": trf, "police_no": "TST-1", "zeyl_no": 0, "yenileme_no": 0,
            "tanzim_tarihi": bugun.isoformat(), "baslama_tarihi": bugun.isoformat(), "bitis_tarihi": (bugun + timedelta(days=20)).isoformat(),
            "brut_prim": "3.600,00", "net_prim": "3400", "komisyon": "510", "taksit_sayisi": 3, "odeme_sekli": "Kredi Kartı"}
    r = c.post("/policeler/yeni", data={**veri, "plaka": ""})
    assert "plaka zorunludur" in r.text
    r = c.post("/policeler/yeni", data={**veri, "plaka": "34TEST123"}, follow_redirects=False)
    assert r.status_code == 303
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    pd = c.get(f"/api/v1/policeler/{pid}").json()
    assert pd["brut_prim"] == 3600.0 and len(pd["taksitler"]) == 3
    # mükerrer anahtar reddedilir
    r = c.post("/policeler/yeni", data={**veri, "plaka": "34TEST123"})
    assert "kayıt var" in r.text
    # 4) taksit tahsil
    sayfa = c.get(f"/policeler/{pid}").text
    assert "Tahsil" in sayfa
    taksit_id = int(sayfa.split("/tahsilat/taksit/")[1].split("/")[0])
    c.post(f"/tahsilat/taksit/{taksit_id}/ode", data={"tahsilat_sekli": "Nakit"})
    pd = c.get(f"/api/v1/policeler/{pid}").json()
    assert pd["taksitler"][0]["odendi"] is True
    # 5) yenileme havuzuna al (20 gün kaldı) -> süreç açılır
    c.post("/yenileme/havuzu-guncelle", data={"gun": 45})
    liste = c.get("/yenileme?gorunum=liste&donem_kodu=tum").text
    assert "Test Müşteri" in liste
    sid = int(liste.split("Test Müşteri")[0].rsplit('href="/hesaplar/', 1)[0].rsplit('/yenileme/', 1)[1].split('"')[0]) if False else None
    # süreç id'sini API ile değil sayfadan bulalım
    import re
    m = re.search(r'/yenileme/(\d+)"[^>]*>Aç</a>', liste.split("Test Müşteri")[1])
    assert m, "süreç satırı bulunamadı"
    sid = int(m.group(1))
    # 6) teklif gir -> pozisyon 'Teklif Alındı'
    c.post(f"/yenileme/{sid}/teklif", data={"sirket_id": tan["sirketler"][1]["id"], "brut_prim": "3200", "odeme_tipi": "Peşin", "taksit_sayisi": 1})
    detay = c.get(f"/yenileme/{sid}").text
    assert "Teklif Alındı" in detay and "3.200,00" in detay
    # 7) yenilendi -> yeni poliçe formu süreçten dolu gelir ve kaydedilince eski poliçe 'Yenilendi' olur
    form = c.get(f"/policeler/yeni?surec_id={sid}").text
    assert 'name="surec_id"' in form and "3200" in form
    r = c.post("/policeler/yeni", data={**veri, "surec_id": sid, "sirket_id": tan["sirketler"][1]["id"], "police_no": "TST-2", "plaka": "34TEST123",
                                        "baslama_tarihi": (bugun + timedelta(days=20)).isoformat(), "bitis_tarihi": (bugun + timedelta(days=385)).isoformat(),
                                        "brut_prim": "3200"}, follow_redirects=False)
    assert r.status_code == 303
    assert c.get(f"/api/v1/policeler/{pid}").json()["durum"] == "Yenilendi"
    assert "Yenilendi" in c.get(f"/yenileme/{sid}").text
    # 8) mesaj gönder (log sağlayıcı)
    r = c.post("/mesajlar/gonder", data={"hesap_id": hid, "kanal": "SMS", "icerik": "Sayın {unvan}, test."}, follow_redirects=False)
    assert r.status_code == 303
    assert "Sayın Test Müşteri, test." in c.get(f"/hesaplar/{hid}?sekme=mesajlar").text
    # 9) talep & görev
    r = c.post("/talepler/yeni", data={"hesap_id": hid, "talep_turu": "Bilgi", "aciklama": "Poliçe kopyası"}, follow_redirects=False)
    tid = int(r.headers["location"].rsplit("/", 1)[1])
    c.post(f"/talepler/{tid}/hareket", data={"durum": "Kapandı", "aciklama": "Gönderildi"})
    assert "Kapandı" in c.get(f"/talepler/{tid}").text
    r = c.post("/ajanda/yeni", data={"baslik": "Ara", "tip": "Arama", "tarih": bugun.isoformat(), "hesap_id": hid}, follow_redirects=False)
    assert r.status_code == 303
    # 10) excel dışa aktar
    r = c.get("/policeler/disa-aktar")
    assert r.status_code == 200 and r.content[:2] == b"PK"


def test_ice_aktar(c):
    csv = ("hes_kod;unvan;tc_no;vergi_no;gsm;sirket_kod;ana_brans_kod;police_no;zeyl_no;yenileme_no;tanzim_tarihi;baslama_tarihi;bitis_tarihi;brut_prim;net_prim;komisyon;taksit_sayisi;plaka;temsilci_kod\n"
           ";İçe Aktarılan Kişi;98765432109;;0533 000 00 00;AXA;KNT;IMP-1;0;0;2026-01-01;2026-01-01;2027-01-01;1500,50;1400;210;1;;T01\n"
           ";Hatalı Satır;;;;YOK;KNT;IMP-2;0;0;2026-01-01;2026-01-01;2027-01-01;1;1;1;1;;\n")
    r = c.post("/policeler/ice-aktar", files={"dosya": ("test.csv", csv.encode("utf-8"), "text/csv")})
    assert r.status_code == 200
    assert "İçe Aktarılan Kişi" in c.get("/hesaplar?q=İçe").text
    assert "Satır 3" in r.text  # hatalı satır raporlanır


def test_potansiyel_surece_al(c):
    tan = c.get("/api/v1/tanimlar").json()
    r = c.post("/potansiyel/yeni", data={"unvan": "Aday Kişi", "gsm": "0534 000 00 00", "ana_brans_id": tan["branslar"][0]["id"], "eski_sirket": "Rakip",
                                         "eski_bitis": (date.today() + timedelta(days=10)).isoformat(), "plaka": "06ADY001"}, follow_redirects=False)
    assert r.status_code == 303
    liste = c.get("/potansiyel").text
    import re
    pid = int(re.search(r'/yenileme/potansiyelden/(\d+)', liste.split("Aday Kişi")[1]).group(1))
    r = c.post(f"/yenileme/potansiyelden/{pid}", follow_redirects=False)
    assert r.status_code == 303 and "/yenileme/" in r.headers["location"]
    assert "Aday Kişi" in c.get("/hesaplar?q=Aday").text  # hesap kartı otomatik açıldı


def test_hatirlatma_kurali(c):
    r = c.post("/mesajlar/kurallari-calistir", follow_redirects=False)
    assert r.status_code == 303
    assert "Gönderildi" in c.get("/mesajlar").text


def test_tanim_crud(c):
    r = c.post("/tanimlar/sirketler", data={"kod": "TST", "ad": "Test Sigorta", "aktif": "1"}, follow_redirects=False)
    assert r.status_code == 303
    assert "Test Sigorta" in c.get("/tanimlar/sirketler").text
    r = c.post("/tanimlar/sirketler", data={"kod": "TST", "ad": "Mükerrer", "aktif": "1"}, follow_redirects=True)
    assert "Kayıt yapılamadı" in r.text


def test_sifre_degistir_ve_rol(c):
    c.post("/tanimlar/kullanicilar", data={"kullanici_adi": "temsilci1", "ad_soyad": "Temsilci Bir", "rol": "temsilci", "sifre": "123456", "aktif": "1"})
    with TestClient(app) as t:
        assert t.post("/login", data={"kullanici_adi": "temsilci1", "sifre": "123456"}, follow_redirects=False).status_code == 303
        assert t.get("/").status_code == 200
        assert t.get("/tanimlar/kullanicilar").status_code == 403
        assert t.get("/policeler/ice-aktar").status_code == 403
