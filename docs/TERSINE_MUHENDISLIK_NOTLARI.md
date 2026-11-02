# PoliSoft LiveLink Pro — İnceleme Notları

Bu belge, `POLISOFT_DOWNLOAD` klasöründeki iki arşivin **salt okunur** incelenmesiyle çıkarılan bulguları özetler.
Amaç, uygulamanın *ne yaptığını* anlayıp OpenAcente'yi bağımsız olarak tasarlamaktı. Hiçbir dosya değiştirilmedi,
hiçbir kod kopyalanmadı; çıkarımlar ikili dosyalardaki metin dizgileri, form kaynakları ve küçük .NET yardımcı
araçlarının decompile çıktısından yapılmıştır.

## 1. Paket içeriği

| Dosya | Boyut | Tür | Not |
|---|---|---|---|
| `PoliSoftLiveLinkPro.zip` → `PoliSoftLiveLinkPro.exe` | 96 MB | Win32 PE, **Delphi** (VCL) | Ana uygulama. DevExpress (cxGrid, Ribbon, Scheduler, Spreadsheet, PDF viewer), FireDAC + Devart MySQL, FastReport, Indy, OpenSSL, TeeChart, oExport bileşenleri gömülü. ~400 form (DFM) kaynağı. |
| `chdrv.zip` → `BackService.exe` | 10 KB | .NET WinForms | Gizli pencere; 5 sn'de bir `PolisoftTriggers.exe` ve mesai saatlerinde `KuyrukTakibi.exe` çalışıyor mu bakar, yoksa `runas` ile başlatır; kendini `HKCU\...\Run`'a ekler. |
| `chromedriver_updater.exe` | 28 KB | .NET WinForms | Kurulu Chrome sürümünü okuyup uygun `chromedriver.exe`'yi (Google "chrome-for-testing" JSON'u veya polisoft sunucusu) indirir. |
| `chromedriver.exe` | 21 MB | Selenium ChromeDriver | Şirket portallarına robotla girip poliçe/teklif çekmek için. |
| `INET.Crypto.dll` | 20 KB | .NET | DES (sabit anahtar 1..8 / IV 8..1) ve TripleDES (sabit parola) ile Base64 şifreleme. Konfigürasyon parolalarını saklamak için kullanılıyor. **Güvenlik açısından zayıf.** |
| `Devart.Data(.MySql).dll`, `MySql.Data.dll`, `Newtonsoft.Json.dll`, `zxing.dll` | | | MySQL erişimi, JSON, barkod/QR. |

Sonuç: **Klasik 2 katmanlı (fat client) mimari** — Delphi masaüstü istemci doğrudan MySQL'e bağlanır; yardımcı .NET
servisler aynı veritabanını kullanır. Lisans/aktivasyon ve güncelleme `service.polisoft.com.tr` SOAP servisinden yapılır.

## 2. Ürün adı ve alanı

* Ürün: **PoliSoft LiveLink** (ana pencere başlığı), "Pro" sürümü. Giriş ekranında şirket adı + kullanıcı + parola; TOTP (`otpauth://totp/LiveLink`) iki faktörlü doğrulama var.
* Alan: **Sigorta acentesi otomasyonu** (Türkiye). Branşlar: Trafik, Kasko, Konut, DASK, Sağlık, Ferdi Kaza, İşyeri, Nakliyat, Hayat/BES, Seyahat.

## 3. Modül haritası (form adlarından)

| PoliSoft formu | İşlev | OpenAcente karşılığı |
|---|---|---|
| `frmLoginEx`, `frmTFALogin` | Giriş, 2FA | `/login` (2FA yol haritasında) |
| `frmMainFrame` ("Süreç İşlemleri" ribbon) | Ana çerçeve | `base.html` yan menü |
| `frmHesapKarti(_Modal)`, `frmTelefonEkle`, `frmYetkiliEkle`, `frmAracKarti`, `frmKVKK*` | Müşteri kartı, telefon/yetkili/araç, KVKK | `/hesaplar/*` |
| `frmPolice`, `frmPoliceArama`, `frmGlobalPoliceIzle`, `frmIptalGir` | Poliçe giriş/arama/izleme/iptal | `/policeler/*` |
| `frmDisPoliceListesi` ("Potansiyel Satış"), `frmDisExcel` | Dış poliçeler, Excel'den alma | `/potansiyel/*`, içe aktarım |
| `frmYenilemeDetay` ("Yenileme - Satış"), `frmYenilemeSureci*`, `frmTeklif`, `frmTeklifTeminatOzellestir`, `frmKarsilastirmaTablosu` | Yenileme süreci, pozisyonlar, teklif karşılaştırma | `/yenileme/*` (kanban + teklif) |
| `frmTahsilatGir`, `frmPBSTahsilatListe`, `frmPBSPoliceListe`, `frmTopluPBS` | PBS (poliçe bilgi/tahsilat sistemi) | `/tahsilat/*` |
| `frmAjanda`, `frmRandevuZiyaretKayit`, `frmGorevlendirme` | Ajanda, randevu, görevlendirme | `/ajanda/*` |
| `frmTalepGirisi`, `frmTalepListe`, `frmCagri*`, `frmCTIAyarlari` | Talep, çağrı merkezi (CTI) | `/talepler/*`, hesap kartı çağrı sekmesi |
| `frmGlobalSMSDialog`, `frmTopluMesajDialog`, `frmSMSSablonlari`, `frmAlertTanim`, `frmInteraktifSMSTanimlari`, `frmWMesaj*` | SMS/e-posta/WhatsApp, şablon, alarm kuralları | `/mesajlar/*` |
| `frmDashboardDetay_*`, `frmWebRapor`, FastReport tasarımları | Dashboard, raporlar | `/`, `/raporlar/*` |
| `frmHedefTanimlari`, `frmHedefIzle`, `frmKampanyaYonetimi`, `frmKupon*` | Hedef & kampanya | yol haritası |
| `frmOps*` (OPS = online poliçe sistemi), `frmTramerQuery`, `frmEGMSorgu`, `frmGenelTrafikSorgu` | Şirket portalı robotları (Selenium), Tramer/SBM/EGM sorguları | yol haritası (API erişimi gerekir) |
| `frmDosyaYonetimi`, `frmDosyaIzleme` | Dosya ekleri | `/dosyalar/*` |
| `frmGrupTanimlari`, `frmNesneTanimlari`, `frmSabitListe`, `frmKuralTanimlari` | Tanımlar | `/tanimlar/*` |

## 4. Veritabanı (MySQL) — gözlemlenen tablolar

Sorgu dizgilerinden ~150 tablo adı çıkarıldı. En çok başvurulanlar ve OpenAcente eşlemesi:

| PoliSoft tablosu | İçerik (kolonlardan) | OpenAcente |
|---|---|---|
| `hesapkart` (`hes_kod`, `hes_ad1`, `htipadi`, `vergi_no`, `temsilci`, `tali`, `sube`, `meslek`, `dogum_tar`…) | Tüm cari kartlar: müşteri, sigorta şirketi, tali acente, banka aynı tabloda (`htipadi` ile ayrılır) | `hesap`, `sigorta_sirketi`, `tali_acente`, `temsilci`, `sube` (ayrı tablolar) |
| `telefonpool`, `adrespool`, `epostapool`, `yetkili`, `arac`, `hesapkimlik`, `hesapkvkk`, `hesapnot` | Kartın alt kayıtları | `hesap_telefon`, `hesap_eposta`, `hesap_yetkili`, `arac`, `hesap.kvkk_*`, `hesap.notlar` |
| `police` (`poli_id`, `sirket_kodu`, `police_no`, `zeyl_no`, `tecditno`, `tanzim`, `bas_tar`, `bit_tar`, `brut_tutar`, `anabrans`, `arabrans`, `plaka`, `temsilci`, `tali`, `pozisyon`, `yenilemekodu`…) | Poliçeler | `police` |
| `policeturu`, `arabrans`, `brans`, `teminatturu`, `policeye_teminat` | Şirket bazlı ürün/branş/teminat kodları | `ana_brans`, `ara_brans` (teminat matrisi yol haritasında) |
| `dispolice` (`esirket`, `eacente`, `epoliceno`, `etanzim`, `ebaslama`, `ebitis`, `ebrut_tl`, plaka/araç alanları) | Dış (rakip) poliçeler = potansiyel | `potansiyel` |
| `pyshareket` (`pid`, `epid`, `poz`, `tarih`, `kullanici`, `aciklama`), `pysdonem` (`donem` = `MM-YYYY`), `pysgrup`, `pysteklif` (`skod`, `ptutar`, `ttutar`, `teklifno`, `pkom`, `tkom`, `odemetip`, `sec`), `pysaltaciklama` | Yenileme süreci hareketleri, dönem, grup, teklif | `yenileme_sureci`, `yenileme_hareket`, `teklif` |
| `pbs_police`, `pbs_tahsilat` (`tahsilat_sekli`, `tahsilat_durumu`, kart/bloke/vade alanları), `pbs_param`, `lwg_odemekural` | Poliçe bilgi & tahsilat sistemi | `tahsilat`, `taksit` |
| `jobs` (DevExpress scheduler alanları), `randevu`, `randevuhareket`, `talep`, `talephareket`, `cagri`, `cagrihareket`, `ctilog` | Ajanda, randevu, talep, çağrı | `gorev`, `talep`, `talep_hareket`, `cagri` |
| `iletidoc`, `wmesaj`, `kvkk_ssablon`, `kvkk_fsablon`, `alert`, `alertusers`, `gsmverify`, `epostaverify` | İleti logu, WhatsApp, şablonlar, alarm kuralları, doğrulama | `mesaj`, `mesaj_sablon`, `hatirlatma_kurali`, `hatirlatma_gonderim` |
| `userfiles`, `dbdosya.pfiles`, `iletidoc.docyer` | Dosyalar (ayrı `dbdosya` şemasında BLOB) | `dosya` (diskte) |
| `llpano`, `lltanimlog`, `polilog`, `weblog` | İşlem/pano logları | `islem_log` |
| `usrs`, `dbuser`, `userparams`, `yetkili`, `temsilcirule`, `extkesleme` | Kullanıcı, parametre, temsilci-kullanıcı eşleme | `kullanici`, `parametre` |
| `hedef`, `cmp_cupon*`, `kampanya*`, `cmmatris` | Hedef & kampanya | yol haritası |
| `ops_*`, `tq_trafik`, `tq_kasko`, `tramersa`, `trm_havuz`, `aptns`, `ptns` | Portal robotu parametreleri, Tramer sonuçları | yol haritası |
| `hesapozelsaha`, `policeozelsaha`, `pbsozelsaha` (`i1..i5, vc1..vc5, m1..m5, lst1..lst5, d1..d5, c1..c5`) | Kullanıcı tanımlı özel alanlar | yol haritası |
| `gorunum`, `vglayoutlist`, `hosview` | Grid görünüm kayıtları | — |

Tipik bir sorgu örneği (dönem mantığını gösterir):

```sql
SELECT ... IF(YEAR(p.ebitis)<>1899, CONCAT(LPAD(MONTH(p.ebitis),2,"0"),"-",YEAR(p.ebitis)),"") as ydonem ... FROM dispolice p
```

→ OpenAcente'de `utils.donem()` aynı `MM-YYYY` biçimini üretir.

## 5. Dış entegrasyonlar (URL dizgilerinden)

* **SBM / Tramer**: `online.sbm.org.tr/trm-police/...`, `ovm-police`, `trm-teklif/...trafikTeklifYenileme` — captcha + 2FA'lı oturumla trafik/kasko poliçe sorgusu, tramer bilgi.
* **Şirket web servisleri**: Anadolu Sigorta SWEP (`swep.anadolusigorta.com.tr/server/cms/PR_SWEP_...`) prim hesaplama; diğer şirketler Selenium robotuyla.
* **SMS**: SMS Makinesi, İletişim Makinesi, Hermes, LeadInPlus, Artı Mesaj — SOAP/REST.
* **Faks**: Interfax. **KVKK onay**: `panel.artikvkk.com`. **Ödeme**: `merchantsafeunipay.com` (sanal POS). **Kısa link**: `psurl.in`.
* **Lisans/güncelleme**: `service.polisoft.com.tr/psAdmin.dll` (SOAP), `polisoft.com.tr/download/skps/`.

OpenAcente bu servislerin hiçbirine bağlanmaz; mesaj gönderimi soyut bir sağlayıcı arayüzü (`services/mesaj_servisi.py`) üzerinden yapılır.

## 6. Tasarım kararları (neden farklı?)

| PoliSoft | OpenAcente | Gerekçe |
|---|---|---|
| Delphi masaüstü, Windows'a bağlı, DevExpress lisansı | Web (FastAPI + Jinja2), her işletim sistemi, tarayıcıdan | Açık kaynak, kurulum kolaylığı, çoklu kullanıcı |
| İstemci doğrudan MySQL'e bağlanır | Sunucu üzerinden, oturum + rol kontrolü | Güvenlik, ağ bağımsızlığı |
| Tek `hesapkart` tablosunda tüm cari tipleri | Ayrı tablolar | Okunabilirlik, bütünlük kısıtları |
| Sabit anahtarlı DES ile saklanan parolalar | PBKDF2-SHA256 özet | Güvenlik |
| Ticari SMS sağlayıcıları sabit kodlu | Takılabilir sağlayıcı | Bağımsızlık |
| Selenium robotu ile portal otomasyonu | Yol haritası (eklenti) | Hukuki/teknik kırılganlık; çekirdeğe alınmadı |
| Özel alanlar `i1..c5` sabit kolonlar | Yol haritası (JSON alan) | Esneklik |

## 7. Yöntem

1. Arşivler geçici dizine açıldı (`unzip`), orijinal klasöre dokunulmadı.
2. `file`/PE başlığı ile dosya türleri belirlendi.
3. Ana exe'den ASCII/UTF-16 dizgiler çıkarıldı (~1.2 M dizgi); sınıf adları (`TfrmXxx`), SQL cümleleri (`SELECT/INSERT/UPDATE` ~2.500 adet), URL'ler filtrelendi.
4. PE kaynak bölümünden RCDATA olarak gömülü 399 binary DFM (form tanımı) çıkarılıp metne dönüştürüldü; `Caption`, `Hint`, `FieldName` değerlerinden ekran alanları okundu.
5. .NET yardımcı araçlar ILSpy ile decompile edildi.
6. Bulgular bu belgeye ve OpenAcente'nin veri modeline aktarıldı.
