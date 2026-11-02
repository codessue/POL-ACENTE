# OpenAcente

**Açık kaynak sigorta acentesi yönetim sistemi.** Türkiye'deki sigorta acentelerinin günlük işini
(müşteri kartı, poliçe takibi, yenileme süreci, tahsilat, hatırlatma, talep/hasar takibi, raporlama)
tek bir web uygulamasında toplar. Ticari "acente otomasyonu" ürünlerinin (ör. PoliSoft LiveLink) iş akışı
incelenerek sıfırdan, bağımsız bir kod tabanı olarak yazılmıştır. Lisans: MIT.

> Kurulum 2 dakika: Python 3.11+ yeterli, veritabanı sunucusu gerekmez (SQLite). İsteğe bağlı MySQL / PostgreSQL.

## Özellikler

| Modül | Ne yapar |
|---|---|
| **Dashboard** | Aktif poliçe, aylık üretim/komisyon, 7-30 gün içinde bitecekler, vadesi geçmiş taksitler, yenileme oranı, branş/şirket dağılımı, bugünkü görevler |
| **Hesap Kartları** | Bireysel/kurumsal müşteri, TC/VKN, çoklu telefon-e-posta, yetkililer, araçlar, KVKK onayı, notlar, tüm geçmiş tek ekranda (sekmeli) |
| **Poliçeler** | Şirket + branş + poliçe/zeyl/yenileme no, prim-komisyon, taksit planı, plaka/riziko, iptal, yenileme zinciri, Excel/CSV dışa aktarım, CSV/XLSX **içe aktarım** |
| **Yenileme Süreci** | Bitişi yaklaşan poliçeler otomatik havuza alınır; kanban panosu (Bekliyor → Arandı → Teklif Alındı → Teklif Sunuldu → Yenilendi/Kaybedildi); şirket bazlı teklif karşılaştırma; tek tıkla yeni poliçeye dönüştürme |
| **Potansiyel Satış** | Başka acentedeki (dış) poliçeler, çapraz satış adayları; sürece alınca hesap kartı otomatik açılır |
| **Tahsilat** | Vadesi geçmiş / yaklaşan taksitler, tek tıkla tahsil, serbest tahsilat, iade, tahsilat geçmişi |
| **Ajanda** | Görev, arama, randevu, ziyaret; gün/hafta/ay görünümü, gecikmiş görev uyarısı |
| **Talepler** | Hasar, zeyil, iptal, bilgi vb. talepler; durum hareketleri, dosya ekleri |
| **Mesajlar** | SMS / e-posta / WhatsApp şablonları, değişkenli içerik, tekil ve toplu gönderim, **otomatik hatırlatma kuralları** (bitişe N gün kala), KVKK filtresi, gönderim logu |
| **Raporlar** | Şirket/branş/temsilci/ay bazlı üretim, yenileme oranları, tahsilat durumu, iptal ve kayıp listeleri; Excel/CSV/yazdır |
| **Tanımlar** | Şube, temsilci, sigorta şirketi, tali acente, ana/ara branş, kullanıcı & rol, parametreler, işlem logları |
| **JSON API** | `/api/v1/...` (hesaplar, poliçeler, yenileme özeti, tanımlar) + `/api/docs` Swagger |

## Hızlı Başlangıç

```bash
git clone <repo> OpenAcente && cd OpenAcente
python -m venv .venv
# Windows: .venv\Scripts\activate   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

veya Windows'ta `run.bat`, Linux/macOS'ta `./run.sh`.

Tarayıcı: <http://127.0.0.1:8000> — kullanıcı **admin**, parola **admin** (ilk girişten sonra değiştirin).

İlk açılışta tablolar oluşturulur; `DEMO_VERI=1` (varsayılan) ise 40 müşteri, ~80 poliçe, potansiyel kayıtlar, görev ve talep örnekleri yüklenir.
Boş başlamak için `.env` dosyasına `DEMO_VERI=0` yazın (veritabanı dosyasını silip yeniden başlatın).

## Yapılandırma (`.env`)

`.env.example` dosyasını `.env` olarak kopyalayın.

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/openacente.db` | `mysql+pymysql://u:p@host/db?charset=utf8mb4` veya `postgresql+psycopg://...` (sürücüyü pip ile kurun) |
| `SECRET_KEY` | (değiştirin) | Oturum çerezi imzası |
| `YENILEME_GUN` | `45` | Bitişine bu kadar gün kalan poliçeler yenileme havuzuna alınır |
| `MESAJ_SAGLAYICI` | `log` | `log` (göndermez, kaydeder) · `smtp` (e-posta) · `http_sms` (JSON POST eden SMS ağ geçidi) |
| `SMTP_*`, `SMS_HTTP_*` | | Sağlayıcı bilgileri |
| `DEMO_VERI` | `1` | İlk kurulumda örnek veri |

## Zamanlanmış görevler

Cron / Görev Zamanlayıcı ile günde bir kez:

```bash
python -m app.gorevler havuz         # bitişi yaklaşanları yenileme sürecine al
python -m app.gorevler hatirlat      # hatırlatma kurallarını çalıştır (SMS/e-posta)
python -m app.gorevler suresi-dolan  # bitişi geçmiş aktif poliçeleri işaretle
python -m app.gorevler sifre-sifirla admin yeniParola
```

## Mimari

```
app/
  main.py            FastAPI uygulaması, oturum, yönlendirmeler
  config.py          .env / ortam değişkenleri
  database.py        SQLAlchemy engine & session
  models.py          Veri modeli (30 tablo)
  auth.py            PBKDF2 parola, oturum, rol kontrolü
  seed.py            İlk kurulum + demo verisi
  gorevler.py        CLI (cron görevleri)
  routers/           Modül başına bir router (hesaplar, policeler, yenileme, ...)
  services/          İş kuralları: yenileme, hatırlatma, mesaj sağlayıcı, içe/dışa aktarım
  templates/         Jinja2 şablonları (sunucu taraflı, harici JS kütüphanesi yok)
  static/            CSS + küçük yardımcı JS
tests/               pytest uçtan uca testler (TestClient + geçici SQLite)
docs/                Tersine mühendislik notları ve veri modeli eşlemesi
```

* **Python 3.11+**, FastAPI, SQLAlchemy 2, Jinja2, openpyxl. Tarayıcı tarafında framework yok; sayfalar sunucuda üretilir, internet bağlantısı gerekmez.
* Roller: `admin` (her şey), `yonetici` (tanımlar, silme, içe aktarım, kullanıcılar), `temsilci` (günlük işlemler).
* Her kritik işlem `islem_log` tablosuna yazılır (kim, ne zaman, ne).

## Testler

```bash
pytest
```

48 test: giriş/yetki, tüm sayfaların açılması, hesap → araç → poliçe → tahsilat → yenileme süreci → teklif → yeni poliçe akışı,
içe aktarım, potansiyel → süreç, hatırlatma kuralı, tanım CRUD, rol kısıtları.

## Yol haritası / katkı

- [ ] Sigorta şirketi portallarından otomatik poliçe çekme (PoliSoft'ta chromedriver/Selenium ile yapılıyor) — eklenti arayüzü `services/` altında tasarlanacak
- [ ] SBM / Tramer sorgu entegrasyonu (resmî API erişimi gerektirir)
- [ ] PDF poliçe/teklif çıktısı
- [ ] Çoklu acente (şube bazlı veri izolasyonu)
- [ ] Mobil uyumlu PWA

Pull request ve issue'lar memnuniyetle karşılanır. Kod ve arayüz dili Türkçedir; tanımlayıcılar ASCII (ş→s, ı→i) yazılır.

## Lisans

MIT — bkz. [LICENSE](LICENSE). Bu proje PoliSoft veya başka bir ticari ürünle ilişkili değildir; hiçbir ticari koddan kopya içermez.
