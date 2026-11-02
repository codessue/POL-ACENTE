"""Hesap kartları (müşteriler) - PoliSoft 'frmHesapKarti' karşılığı."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli, yonetici_gerekli
from ..database import get_db
from ..services import disa_aktar
from ..templating import render
from ..utils import flash, logla, tam, tarih
from .ortak import bos, bul, sayfala, secenekler

router = APIRouter(prefix="/hesaplar", tags=["hesaplar"])


def _sorgu(q: str, tip: str, temsilci_id: Optional[int], kvkk: str):
    H = models.Hesap
    s = select(H).options(selectinload(H.telefonlar), selectinload(H.temsilci)).where(H.aktif.is_(True))
    if q:
        like = f"%{q.strip()}%"
        tel_alt = select(models.HesapTelefon.hesap_id).where(models.HesapTelefon.numara.like(like))
        plaka_alt = select(models.Arac.hesap_id).where(models.Arac.plaka.like(like.upper().replace(" ", "")))
        s = s.where(or_(H.unvan.like(like), H.hes_kod.like(like), H.tc_no.like(like), H.vergi_no.like(like),
                        H.id.in_(tel_alt), H.id.in_(plaka_alt)))
    if tip:
        s = s.where(H.tip == tip)
    if temsilci_id:
        s = s.where(H.temsilci_id == temsilci_id)
    if kvkk == "var":
        s = s.where(H.kvkk_onay.is_(True))
    elif kvkk == "yok":
        s = s.where(H.kvkk_onay.is_(False))
    return s.order_by(H.unvan)


@router.get("")
def liste(request: Request, q: str = "", tip: str = "", temsilci_id: Optional[int] = None, kvkk: str = "", sayfa: int = 1,
          k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    sonuc = sayfala(db, _sorgu(q, tip, temsilci_id, kvkk), sayfa)
    return render(request, "hesaplar/liste.html", **sonuc, q=q, tip=tip, temsilci_id=temsilci_id, kvkk=kvkk, **secenekler(db))


@router.get("/disa-aktar")
def disa(q: str = "", tip: str = "", temsilci_id: Optional[int] = None, kvkk: str = "",
         k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    kayitlar = db.scalars(_sorgu(q, tip, temsilci_id, kvkk)).all()
    kolon = ["Hesap Kodu", "Ünvan", "Tip", "TC/VKN", "GSM", "E-Posta", "İl", "İlçe", "Temsilci", "KVKK", "Aktif Poliçe"]
    satir = [(h.hes_kod, h.unvan, h.tip, h.kimlik_no, h.gsm, h.eposta, h.il, h.ilce, h.temsilci.ad_soyad if h.temsilci else "",
              "Evet" if h.kvkk_onay else "Hayır", sum(1 for p in h.policeler if p.durum == "Aktif")) for h in kayitlar]
    veri = disa_aktar.excel_bytes("Hesaplar", kolon, satir)
    return Response(veri, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=hesaplar_{date.today()}.xlsx"})


@router.get("/yeni")
def yeni_form(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    return render(request, "hesaplar/form.html", h=None, onerilen_kod=disa_aktar.yeni_hes_kod(db), **secenekler(db))


def _formdan(h: models.Hesap, f: dict, db: Session) -> Optional[str]:
    h.hes_kod = (f.get("hes_kod") or "").strip().upper() or disa_aktar.yeni_hes_kod(db)
    h.tip = f.get("tip") or "Bireysel"
    h.unvan = (f.get("unvan") or "").strip()
    if not h.unvan:
        return "Ünvan / Ad Soyad zorunludur."
    h.tc_no = bos(f.get("tc_no"))
    h.vergi_no = bos(f.get("vergi_no"))
    if h.tc_no and (len(h.tc_no) != 11 or not h.tc_no.isdigit()):
        return "TC Kimlik No 11 haneli rakam olmalıdır."
    if h.vergi_no and (len(h.vergi_no) not in (10, 11) or not h.vergi_no.isdigit()):
        return "Vergi No 10 haneli rakam olmalıdır."
    h.vergi_dairesi = bos(f.get("vergi_dairesi"))
    h.dogum_tarihi = tarih(f.get("dogum_tarihi"))
    h.cinsiyet = bos(f.get("cinsiyet"))
    h.meslek = bos(f.get("meslek"))
    h.il = bos(f.get("il"))
    h.ilce = bos(f.get("ilce"))
    h.adres = bos(f.get("adres"))
    h.grup = bos(f.get("grup"))
    h.referans = bos(f.get("referans"))
    h.temsilci_id = tam(f.get("temsilci_id"))
    h.sube_id = tam(f.get("sube_id"))
    h.tali_id = tam(f.get("tali_id"))
    h.notlar = bos(f.get("notlar"))
    onay = f.get("kvkk_onay") == "1"
    if onay and not h.kvkk_onay:
        h.kvkk_tarih = date.today()
        h.kvkk_kanal = f.get("kvkk_kanal") or "Islak İmza"
    h.kvkk_onay = onay
    if not onay:
        h.kvkk_tarih, h.kvkk_kanal = None, None
    return None


@router.post("/yeni")
async def yeni(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = dict(await request.form())
    h = models.Hesap(olusturan=k.kullanici_adi)
    hata = _formdan(h, f, db)
    if not hata and db.scalar(select(models.Hesap).where(models.Hesap.hes_kod == h.hes_kod)):
        hata = f"{h.hes_kod} hesap kodu zaten kullanılıyor."
    if hata:
        flash(request, hata, "hata")
        return render(request, "hesaplar/form.html", h=h, onerilen_kod=h.hes_kod, **secenekler(db))
    gsm = bos(f.get("gsm"))
    if gsm:
        h.telefonlar.append(models.HesapTelefon(tip="GSM", numara=gsm))
    ep = bos(f.get("eposta"))
    if ep:
        h.epostalar.append(models.HesapEposta(adres=ep))
    db.add(h)
    db.flush()
    logla(db, k, "Hesap kartı açıldı", "hesap", h.id, h.unvan)
    db.commit()
    flash(request, f"{h.unvan} kartı oluşturuldu.")
    return RedirectResponse(f"/hesaplar/{h.id}", status_code=303)


@router.get("/{hid}")
def detay(request: Request, hid: int, sekme: str = "ozet", k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    surecler = list(db.scalars(select(models.YenilemeSureci).where(models.YenilemeSureci.hesap_id == hid).order_by(models.YenilemeSureci.bitis_tarihi.desc())))
    gorevler = list(db.scalars(select(models.Gorev).where(models.Gorev.hesap_id == hid).order_by(models.Gorev.tarih.desc()).limit(50)))
    talepler = list(db.scalars(select(models.Talep).where(models.Talep.hesap_id == hid).order_by(models.Talep.id.desc())))
    cagrilar = list(db.scalars(select(models.Cagri).where(models.Cagri.hesap_id == hid).order_by(models.Cagri.tarih.desc()).limit(50)))
    mesajlar = list(db.scalars(select(models.Mesaj).where(models.Mesaj.hesap_id == hid).order_by(models.Mesaj.tarih.desc()).limit(50)))
    dosyalar = list(db.scalars(select(models.Dosya).where(models.Dosya.yer == "hesap", models.Dosya.yer_id == hid).order_by(models.Dosya.id.desc())))
    tahsilatlar = list(db.scalars(select(models.Tahsilat).where(models.Tahsilat.hesap_id == hid).order_by(models.Tahsilat.tarih.desc()).limit(50)))
    loglar = list(db.scalars(select(models.IslemLog).where(models.IslemLog.yer == "hesap", models.IslemLog.yer_id == hid).order_by(models.IslemLog.id.desc()).limit(30)))
    potansiyeller = list(db.scalars(select(models.Potansiyel).where(models.Potansiyel.hesap_id == hid)))
    sablonlar = list(db.scalars(select(models.MesajSablon).where(models.MesajSablon.aktif.is_(True))))
    return render(request, "hesaplar/detay.html", h=h, sekme=sekme, surecler=surecler, gorevler=gorevler, talepler=talepler,
                  cagrilar=cagrilar, mesajlar=mesajlar, dosyalar=dosyalar, tahsilatlar=tahsilatlar, loglar=loglar,
                  potansiyeller=potansiyeller, sablonlar=sablonlar, **secenekler(db))


@router.get("/{hid}/duzenle")
def duzenle_form(request: Request, hid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    return render(request, "hesaplar/form.html", h=h, onerilen_kod=h.hes_kod, **secenekler(db))


@router.post("/{hid}/duzenle")
async def duzenle(request: Request, hid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    f = dict(await request.form())
    hata = _formdan(h, f, db)
    if hata:
        flash(request, hata, "hata")
        return render(request, "hesaplar/form.html", h=h, onerilen_kod=h.hes_kod, **secenekler(db))
    logla(db, k, "Hesap kartı güncellendi", "hesap", h.id)
    db.commit()
    flash(request, "Kart güncellendi.")
    return RedirectResponse(f"/hesaplar/{h.id}", status_code=303)


@router.post("/{hid}/sil")
def sil(request: Request, hid: int, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    if h.policeler:
        flash(request, "Poliçesi olan kart silinemez; pasife alındı.", "bilgi")
        h.aktif = False
    else:
        db.delete(h)
    logla(db, k, "Hesap kartı silindi/pasife alındı", "hesap", hid, h.unvan)
    db.commit()
    return RedirectResponse("/hesaplar", status_code=303)


# ---- alt kayıtlar
@router.post("/{hid}/telefon")
def telefon_ekle(request: Request, hid: int, tip: str = Form("GSM"), numara: str = Form(...), aciklama: str = Form(""),
                 k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    h.telefonlar.append(models.HesapTelefon(tip=tip, numara=numara.strip(), aciklama=bos(aciklama)))
    db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=iletisim", status_code=303)


@router.post("/{hid}/telefon/{tid}/sil")
def telefon_sil(hid: int, tid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    t = db.get(models.HesapTelefon, tid)
    if t and t.hesap_id == hid:
        db.delete(t)
        db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=iletisim", status_code=303)


@router.post("/{hid}/eposta")
def eposta_ekle(hid: int, adres: str = Form(...), tip: str = Form("Kişisel"), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    h.epostalar.append(models.HesapEposta(adres=adres.strip(), tip=tip))
    db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=iletisim", status_code=303)


@router.post("/{hid}/eposta/{eid}/sil")
def eposta_sil(hid: int, eid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    e = db.get(models.HesapEposta, eid)
    if e and e.hesap_id == hid:
        db.delete(e)
        db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=iletisim", status_code=303)


@router.post("/{hid}/yetkili")
def yetkili_ekle(hid: int, ad_soyad: str = Form(...), gorev: str = Form(""), telefon: str = Form(""), eposta: str = Form(""),
                 k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    h.yetkililer.append(models.HesapYetkili(ad_soyad=ad_soyad.strip(), gorev=bos(gorev), telefon=bos(telefon), eposta=bos(eposta)))
    db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=iletisim", status_code=303)


@router.post("/{hid}/yetkili/{yid}/sil")
def yetkili_sil(hid: int, yid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    y = db.get(models.HesapYetkili, yid)
    if y and y.hesap_id == hid:
        db.delete(y)
        db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=iletisim", status_code=303)


@router.post("/{hid}/arac")
def arac_ekle(request: Request, hid: int, plaka: str = Form(...), marka: str = Form(""), model: str = Form(""), model_yili: str = Form(""),
              kullanim_tarzi: str = Form(""), motor_no: str = Form(""), sasi_no: str = Form(""), tescil_tarihi: str = Form(""),
              k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hid, "Hesap")
    h.araclar.append(models.Arac(plaka=plaka.upper().replace(" ", ""), marka=bos(marka), model=bos(model), model_yili=tam(model_yili),
                                 kullanim_tarzi=bos(kullanim_tarzi), motor_no=bos(motor_no), sasi_no=bos(sasi_no), tescil_tarihi=tarih(tescil_tarihi)))
    logla(db, k, "Araç eklendi", "hesap", hid, plaka)
    db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=araclar", status_code=303)


@router.post("/{hid}/arac/{aid}/sil")
def arac_sil(request: Request, hid: int, aid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    a = db.get(models.Arac, aid)
    if a and a.hesap_id == hid:
        if db.scalar(select(models.Police.id).where(models.Police.arac_id == aid)):
            flash(request, "Bu araca bağlı poliçe var, silinemez.", "hata")
        else:
            db.delete(a)
            db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=araclar", status_code=303)


@router.post("/{hid}/cagri")
def cagri_ekle(hid: int, yon: str = Form("Giden"), telefon: str = Form(""), neden: str = Form(""), sonuc: str = Form(""), sure_sn: str = Form("0"),
               k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    bul(db, models.Hesap, hid, "Hesap")
    db.add(models.Cagri(hesap_id=hid, yon=yon, telefon=bos(telefon), neden=bos(neden), sonuc=bos(sonuc), sure_sn=tam(sure_sn, 0), kullanici=k.kullanici_adi))
    db.commit()
    return RedirectResponse(f"/hesaplar/{hid}?sekme=cagrilar", status_code=303)
