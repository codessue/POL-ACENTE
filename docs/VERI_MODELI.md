# OpenAcente Veri Modeli

```
Sube 1──* Temsilci 1──* Kullanici
                │
Hesap *──1 Temsilci        Hesap 1──* HesapTelefon / HesapEposta / HesapYetkili / Arac
  │
  ├──* Police *──1 SigortaSirketi, AnaBrans, (AraBrans), (Arac), (Temsilci), (TaliAcente), (Sube)
  │      ├──* Taksit
  │      ├──* Tahsilat
  │      └──0..1 YenilemeSureci ──* YenilemeHareket
  │                       └──* Teklif *──1 SigortaSirketi
  ├──* Potansiyel ──0..1 YenilemeSureci
  ├──* Gorev, Talep(──* TalepHareket), Cagri, Mesaj
  └──  Dosya (yer='hesap'), IslemLog (yer='hesap')

MesajSablon 1──* HatirlatmaKurali 1──* HatirlatmaGonderim *──1 Police
Parametre (anahtar/değer)
```

## Tablolar

| Tablo | Amaç | Önemli alanlar |
|---|---|---|
| `kullanici` | Giriş yapan kişi | `kullanici_adi`, `sifre_hash` (PBKDF2), `rol` ∈ {admin, yonetici, temsilci}, `temsilci_id` |
| `sube`, `temsilci`, `sigorta_sirketi`, `tali_acente` | Tanımlar | `kod` tekil, `aktif` |
| `ana_brans`, `ara_brans` | Branş hiyerarşisi | `arac_gerekli` → plaka zorunlu |
| `parametre` | Ayarlar | `acente_unvan`, `varsayilan_komisyon_orani` … |
| `hesap` | Müşteri kartı | `hes_kod` tekil, `tip`, `unvan`, `tc_no`, `vergi_no`, `kvkk_onay/tarih/kanal`, `temsilci_id` |
| `hesap_telefon`, `hesap_eposta`, `hesap_yetkili`, `arac` | Alt kayıtlar | `arac.plaka` indeksli |
| `police` | Poliçe | tekil anahtar (`sirket_id`,`police_no`,`zeyl_no`,`yenileme_no`); `durum` ∈ {Aktif, İptal, Yenilendi, Süresi Doldu}; `onceki_police_id` yenileme zinciri; `kaynak` |
| `taksit` | Ödeme planı | `sira`, `vade`, `tutar`, `odendi` |
| `tahsilat` | Gerçekleşen tahsilat | `tahsilat_sekli`, `durum` ∈ {Tahsil Edildi, Bekliyor, İade} |
| `yenileme_sureci` | Yenileme / satış takibi | `donem` (MM-YYYY), `pozisyon` ∈ {Bekliyor, Arandı, Teklif Alındı, Teklif Sunuldu, Yenilendi, Kaybedildi, İptal}, `police_id` **veya** `potansiyel_id`, `yeni_police_id` |
| `yenileme_hareket` | Süreç zaman çizgisi | `pozisyon`, `aciklama`, `kullanici` |
| `teklif` | Şirket teklifi | `brut_prim`, `net_prim`, `komisyon`, `secildi` |
| `potansiyel` | Dış poliçe / aday | `eski_*` alanları, `durum` ∈ {Açık, Sürece Alındı, Kazanıldı, Kaybedildi} |
| `gorev` | Ajanda | `tip`, `tarih`, `saat`, `atanan_id`, `durum` |
| `talep`, `talep_hareket` | Müşteri talebi | `talep_turu`, `durum` ∈ {Açık, İşlemde, Kapandı} |
| `cagri` | Çağrı kaydı | `yon`, `neden`, `sonuc`, `sure_sn` |
| `mesaj_sablon` | Şablon | `kanal`, `icerik` (`{unvan}` vb. değişkenler) |
| `mesaj` | Gönderim logu | `kanal`, `alici`, `durum`, `hata` |
| `hatirlatma_kurali`, `hatirlatma_gonderim` | Otomatik hatırlatma | `gun_once`; gönderim tablosu tekrarları engeller |
| `dosya` | Ek | `yer` ∈ {hesap, police, talep, potansiyel}, `yer_id`, diskte `data/uploads/<yer>/<uuid>` |
| `islem_log` | Denetim izi | `kullanici`, `islem`, `yer`, `yer_id`, `aciklama` |

## Temel iş kuralları

* **Yenileme havuzu**: `YenilemeSureci` kaydı olmayan, `durum='Aktif'`, bitişine ≤ `YENILEME_GUN` kalan poliçeler otomatik sürece alınır (`services/yenileme_servisi.surece_al`).
* **İlk teklif** girildiğinde pozisyon `Bekliyor/Arandı` → `Teklif Alındı`; bir teklif "seçilince" → `Teklif Sunuldu`.
* **Yenilendi**: süreçten "Poliçe Gir" ile açılan form seçili teklifle dolu gelir; kaydedilince eski poliçe `Yenilendi`, yeni poliçe `kaynak='Yenileme'`, `yenileme_no+1`, `onceki_police_id` bağlanır.
* **Taksit planı** poliçe kaydında brüt prim / taksit sayısına göre aylık üretilir; ödenmiş taksit varsa yeniden üretilmez.
* **Serbest tahsilat** tutarı açık taksitleri sırayla kapatır.
* **Otomatik hatırlatma** yalnızca `kvkk_onay=1` müşterilere gider; aynı kural + poliçe için bir kez.
* **Silme**: poliçesi olan hesap, tahsilatı olan poliçe silinmez (pasife alma / uyarı).
