"""Poliçeler - PoliSoft 'frmPolice' / 'frmPoliceArama' / 'frmGlobalPoliceIzle' karşılığı."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli, yonetici_gerekli
from ..database import get_db
from ..services import disa_aktar
from ..templating import render
from ..utils import flash, logla, para, tam, tarih
from .ortak import bos, bul, sayfala, secenekler

router = APIRouter(prefix="/policeler", tags=["policeler"])
DURUMLAR = ["Aktif", "İptal", "Yenilendi", "Süresi Doldu"]
ODEME = ["Peşin", "Kredi Kartı", "Havale", "Senet", "Çek"]


def _sorgu(f: dict):
    P = models.Police
    s = select(P).options(selectinload(P.hesap), selectinload(P.sirket), selectinload(P.ana_brans), selectinload(P.temsilci))
    q = (f.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        hesap_alt = select(models.Hesap.id).where(or_(models.Hesap.unvan.like(like), models.Hesap.hes_kod.like(like),
                                                     models.Hesap.tc_no.like(like), models.Hesap.vergi_no.like(like)))
        s = s.where(or_(P.police_no.like(like), P.plaka.like(like.upper().replace(" ", "")), P.hesap_id.in_(hesap_alt)))
    for alan in ("sirket_id", "ana_brans_id", "temsilci_id", "sube_id", "tali_id"):
        v = tam(f.get(alan))
        if v:
            s = s.where(getattr(P, alan) == v)
    if f.get("durum"):
        s = s.where(P.durum == f["durum"])
    b1, b2 = tarih(f.get("bitis1")), tarih(f.get("bitis2"))
    if b1:
        s = s.where(P.bitis_tarihi >= b1)
    if b2:
        s = s.where(P.bitis_tarihi <= b2)
    t1, t2 = tarih(f.get("tanzim1")), tarih(f.get("tanzim2"))
    if t1:
        s = s.where(P.tanzim_tarihi >= t1)
    if t2:
        s = s.where(P.tanzim_tarihi <= t2)
    sirala = f.get("sirala") or "bitis"
    if sirala == "tanzim":
        s = s.order_by(P.tanzim_tarihi.desc())
    elif sirala == "prim":
        s = s.order_by(P.brut_prim.desc())
    else:
        s = s.order_by(P.bitis_tarihi)
    return s


@router.get("")
def liste(request: Request, sayfa: int = 1, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = dict(request.query_params)
    if "on" in f:  # hızlı filtre: bu hafta/30 gün bitiyor
        gun = tam(f["on"], 30)
        f["bitis1"], f["bitis2"], f["durum"] = str(date.today()), str(date.today() + timedelta(days=gun)), "Aktif"
    sonuc = sayfala(db, _sorgu(f), sayfa)
    toplam_brut = sum((Decimal(str(p.brut_prim or 0)) for p in sonuc["kayitlar"]), Decimal("0"))
    return render(request, "policeler/liste.html", **sonuc, f=f, DURUMLAR=DURUMLAR, toplam_brut=toplam_brut, **secenekler(db))


@router.get("/disa-aktar")
def disa(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = dict(request.query_params)
    kayitlar = db.scalars(_sorgu(f)).all()
    kolon = ["Poliçe No", "Zeyl", "Yenileme", "Şirket", "Branş", "Hesap Kodu", "Sigortalı", "Plaka", "Tanzim", "Başlama", "Bitiş",
             "Brüt Prim", "Net Prim", "Komisyon", "Taksit", "Ödeme", "Temsilci", "Durum"]
    satir = [(p.police_no, p.zeyl_no, p.yenileme_no, p.sirket.ad, p.ana_brans.ad, p.hesap.hes_kod, p.hesap.unvan, p.plaka,
              p.tanzim_tarihi, p.baslama_tarihi, p.bitis_tarihi, p.brut_prim, p.net_prim, p.komisyon, p.taksit_sayisi,
              p.odeme_sekli, p.temsilci.ad_soyad if p.temsilci else "", p.durum) for p in kayitlar]
    if f.get("bicim") == "csv":
        return Response(disa_aktar.csv_bytes(kolon, satir), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=policeler_{date.today()}.csv"})
    return Response(disa_aktar.excel_bytes("Poliçeler", kolon, satir),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=policeler_{date.today()}.xlsx"})


@router.get("/ice-aktar")
def ice_form(request: Request, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    return render(request, "policeler/ice_aktar.html", kolonlar=disa_aktar.POLICE_ICE_AKTAR_KOLONLAR, sonuc=None, **secenekler(db))


@router.get("/ice-aktar/sablon")
def ice_sablon(k: models.Kullanici = Depends(giris_gerekli)):
    ornek = [("H000001", "Ahmet Yılmaz", "12345678901", "", "0532 111 22 33", "ANA", "TRF", "123456", 0, 0,
              "2026-01-10", "2026-01-10", "2027-01-10", "4500,00", "4285,71", "642,86", 1, "34ABC123", "T01")]
    return Response(disa_aktar.csv_bytes(disa_aktar.POLICE_ICE_AKTAR_KOLONLAR, ornek), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=police_ice_aktar_sablon.csv"})


@router.post("/ice-aktar")
async def ice(request: Request, dosya: UploadFile = File(...), k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    icerik = await dosya.read()
    sonuc = disa_aktar.police_ice_aktar(db, dosya.filename or "veri.csv", icerik, k.kullanici_adi)
    logla(db, k, "Poliçe içe aktarımı", "police", None, f"{sonuc['eklenen']} eklendi, {sonuc['atlanan']} atlandı, {len(sonuc['hatalar'])} hata")
    db.commit()
    return render(request, "policeler/ice_aktar.html", kolonlar=disa_aktar.POLICE_ICE_AKTAR_KOLONLAR, sonuc=sonuc, **secenekler(db))


@router.get("/yeni")
def yeni_form(request: Request, hesap_id: Optional[int] = None, surec_id: Optional[int] = None, onceki_id: Optional[int] = None,
              k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    hesap = db.get(models.Hesap, hesap_id) if hesap_id else None
    onceki = db.get(models.Police, onceki_id) if onceki_id else None
    surec = db.get(models.YenilemeSureci, surec_id) if surec_id else None
    if surec and not onceki:
        onceki = surec.police
    if onceki and not hesap:
        hesap = onceki.hesap
    if surec and not hesap:
        hesap = surec.hesap
    secili_teklif = None
    if surec:
        secili_teklif = next((t for t in surec.teklifler if t.secildi), None) or (surec.teklifler[0] if surec.teklifler else None)
    return render(request, "policeler/form.html", p=None, hesap=hesap, onceki=onceki, surec=surec, secili_teklif=secili_teklif,
                  ODEME=ODEME, DURUMLAR=DURUMLAR, **secenekler(db))


def _formdan(p: models.Police, f: dict, db: Session) -> Optional[str]:
    p.hesap_id = tam(f.get("hesap_id"))
    if not p.hesap_id or db.get(models.Hesap, p.hesap_id) is None:
        return "Geçerli bir hesap kartı seçin."
    p.sirket_id = tam(f.get("sirket_id"))
    p.ana_brans_id = tam(f.get("ana_brans_id"))
    p.ara_brans_id = tam(f.get("ara_brans_id"))
    if not p.sirket_id or not p.ana_brans_id:
        return "Sigorta şirketi ve ana branş zorunludur."
    p.police_no = (f.get("police_no") or "").strip()
    if not p.police_no:
        return "Poliçe numarası zorunludur."
    p.zeyl_no = tam(f.get("zeyl_no"), 0)
    p.yenileme_no = tam(f.get("yenileme_no"), 0)
    p.tanzim_tarihi = tarih(f.get("tanzim_tarihi"))
    p.baslama_tarihi = tarih(f.get("baslama_tarihi"))
    p.bitis_tarihi = tarih(f.get("bitis_tarihi"))
    if not (p.tanzim_tarihi and p.baslama_tarihi and p.bitis_tarihi):
        return "Tanzim, başlama ve bitiş tarihleri zorunludur."
    if p.bitis_tarihi <= p.baslama_tarihi:
        return "Bitiş tarihi başlangıçtan sonra olmalıdır."
    p.para_birimi = f.get("para_birimi") or "TRY"
    p.brut_prim = para(f.get("brut_prim"))
    p.net_prim = para(f.get("net_prim")) or p.brut_prim
    p.komisyon = para(f.get("komisyon"))
    p.taksit_sayisi = max(1, tam(f.get("taksit_sayisi"), 1))
    p.odeme_sekli = f.get("odeme_sekli") or "Peşin"
    p.temsilci_id = tam(f.get("temsilci_id"))
    p.tali_id = tam(f.get("tali_id"))
    p.sube_id = tam(f.get("sube_id"))
    p.arac_id = tam(f.get("arac_id"))
    p.plaka = (f.get("plaka") or "").upper().replace(" ", "") or None
    if p.arac_id and not p.plaka:
        a = db.get(models.Arac, p.arac_id)
        p.plaka = a.plaka if a else None
    brans = db.get(models.AnaBrans, p.ana_brans_id)
    if brans and brans.arac_gerekli and not p.plaka:
        return f"{brans.ad} branşı için plaka zorunludur."
    p.riziko_adresi = bos(f.get("riziko_adresi"))
    p.aciklama = bos(f.get("aciklama"))
    if f.get("durum") in DURUMLAR:
        p.durum = f["durum"]
    return None


def _taksit_plani(p: models.Police) -> None:
    p.taksitler.clear()
    n = p.taksit_sayisi or 1
    brut = Decimal(str(p.brut_prim or 0))
    pay = (brut / n).quantize(Decimal("0.01"))
    for i in range(n):
        tutar = pay if i < n - 1 else brut - pay * (n - 1)
        ay = p.baslama_tarihi.month - 1 + i
        vade = date(p.baslama_tarihi.year + ay // 12, ay % 12 + 1, min(p.baslama_tarihi.day, 28))
        p.taksitler.append(models.Taksit(sira=i + 1, vade=vade, tutar=tutar))


@router.post("/yeni")
async def yeni(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = dict(await request.form())
    p = models.Police(olusturan=k.kullanici_adi)
    hata = _formdan(p, f, db)
    if not hata and db.scalar(select(models.Police.id).where(models.Police.sirket_id == p.sirket_id, models.Police.police_no == p.police_no,
                                                              models.Police.zeyl_no == p.zeyl_no, models.Police.yenileme_no == p.yenileme_no)):
        hata = "Aynı şirket / poliçe no / zeyl / yenileme numarası ile kayıt var."
    if hata:
        flash(request, hata, "hata")
        hesap = db.get(models.Hesap, p.hesap_id) if p.hesap_id else None
        return render(request, "policeler/form.html", p=p, hesap=hesap, onceki=None, surec=None, secili_teklif=None, ODEME=ODEME, DURUMLAR=DURUMLAR, **secenekler(db))
    surec = db.get(models.YenilemeSureci, tam(f.get("surec_id"))) if f.get("surec_id") else None
    onceki_id = tam(f.get("onceki_police_id"))
    if surec is not None and surec.acik:
        from ..services import yenileme_servisi
        yenileme_servisi.yenile(db, surec, p, k)
    else:
        if onceki_id:
            p.onceki_police_id = onceki_id
            p.kaynak = "Yenileme"
            onceki = db.get(models.Police, onceki_id)
            if onceki:
                onceki.durum = "Yenilendi"
        db.add(p)
        db.flush()
    _taksit_plani(p)
    logla(db, k, "Poliçe kaydedildi", "police", p.id, f"{p.police_no} / {p.hesap.unvan}")
    db.commit()
    flash(request, f"{p.police_no} numaralı poliçe kaydedildi.")
    return RedirectResponse(f"/policeler/{p.id}", status_code=303)


@router.get("/{pid}")
def detay(request: Request, pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    surec = db.scalar(select(models.YenilemeSureci).where(models.YenilemeSureci.police_id == pid))
    dosyalar = list(db.scalars(select(models.Dosya).where(models.Dosya.yer == "police", models.Dosya.yer_id == pid)))
    mesajlar = list(db.scalars(select(models.Mesaj).where(models.Mesaj.police_id == pid).order_by(models.Mesaj.tarih.desc())))
    sonraki = db.scalar(select(models.Police).where(models.Police.onceki_police_id == pid))
    sablonlar = list(db.scalars(select(models.MesajSablon).where(models.MesajSablon.aktif.is_(True))))
    loglar = list(db.scalars(select(models.IslemLog).where(models.IslemLog.yer == "police", models.IslemLog.yer_id == pid).order_by(models.IslemLog.id.desc())))
    return render(request, "policeler/detay.html", p=p, surec=surec, dosyalar=dosyalar, mesajlar=mesajlar, sonraki=sonraki,
                  sablonlar=sablonlar, loglar=loglar)


@router.get("/{pid}/duzenle")
def duzenle_form(request: Request, pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    return render(request, "policeler/form.html", p=p, hesap=p.hesap, onceki=None, surec=None, secili_teklif=None, ODEME=ODEME, DURUMLAR=DURUMLAR, **secenekler(db))


@router.post("/{pid}/duzenle")
async def duzenle(request: Request, pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    f = dict(await request.form())
    eski = (p.brut_prim, p.taksit_sayisi, p.baslama_tarihi)
    hata = _formdan(p, f, db)
    if hata:
        flash(request, hata, "hata")
        return render(request, "policeler/form.html", p=p, hesap=p.hesap, onceki=None, surec=None, secili_teklif=None, ODEME=ODEME, DURUMLAR=DURUMLAR, **secenekler(db))
    if (p.brut_prim, p.taksit_sayisi, p.baslama_tarihi) != eski and not any(t.odendi for t in p.taksitler):
        _taksit_plani(p)
    logla(db, k, "Poliçe güncellendi", "police", p.id)
    db.commit()
    flash(request, "Poliçe güncellendi.")
    return RedirectResponse(f"/policeler/{p.id}", status_code=303)


@router.post("/{pid}/iptal")
def iptal(request: Request, pid: int, iptal_tarihi: str = Form(""), iptal_nedeni: str = Form(""),
          k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    p.durum = "İptal"
    p.iptal_tarihi = tarih(iptal_tarihi) or date.today()
    p.iptal_nedeni = bos(iptal_nedeni)
    surec = db.scalar(select(models.YenilemeSureci).where(models.YenilemeSureci.police_id == pid))
    if surec and surec.acik:
        from ..services import yenileme_servisi
        yenileme_servisi.pozisyon_degistir(db, surec, "İptal", "Poliçe iptal edildi", k)
    logla(db, k, "Poliçe iptal edildi", "police", pid, p.iptal_nedeni or "")
    db.commit()
    flash(request, "Poliçe iptal edildi.", "bilgi")
    return RedirectResponse(f"/policeler/{pid}", status_code=303)


@router.post("/{pid}/sil")
def sil(request: Request, pid: int, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    if p.tahsilatlar:
        flash(request, "Tahsilatı olan poliçe silinemez.", "hata")
        return RedirectResponse(f"/policeler/{pid}", status_code=303)
    for s in db.scalars(select(models.YenilemeSureci).where(or_(models.YenilemeSureci.police_id == pid, models.YenilemeSureci.yeni_police_id == pid))):
        db.delete(s)
    hid = p.hesap_id
    db.delete(p)
    logla(db, k, "Poliçe silindi", "police", pid, p.police_no)
    db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=policeler", status_code=303)


@router.post("/{pid}/taksit-plani")
def taksit_yenile(request: Request, pid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    p = bul(db, models.Police, pid, "Poliçe")
    if any(t.odendi for t in p.taksitler):
        flash(request, "Ödenmiş taksit var, plan yeniden oluşturulamaz.", "hata")
    else:
        _taksit_plani(p)
        db.commit()
        flash(request, "Taksit planı yeniden oluşturuldu.")
    return RedirectResponse(f"/policeler/{pid}", status_code=303)
