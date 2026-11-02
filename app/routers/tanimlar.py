"""Tanımlar: şubeler, temsilciler, şirketler, tali acenteler, branşlar, kullanıcılar, parametreler, işlem logları."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli, sifre_ozetle, yonetici_gerekli
from ..database import get_db
from ..templating import render
from ..utils import flash, logla, para, tam
from .ortak import bos, bul, sayfala, secenekler

router = APIRouter(prefix="/tanimlar", tags=["tanimlar"])

# Her tanım türü için: model, başlık, alanlar (ad, etiket, tür, seçenek kaynağı)
TANIMLAR = {
    "subeler": (models.Sube, "Şubeler", [("kod", "Kod", "text", None), ("ad", "Şube Adı", "text", None), ("aktif", "Aktif", "bool", None)]),
    "temsilciler": (models.Temsilci, "Temsilciler", [("kod", "Kod", "text", None), ("ad_soyad", "Ad Soyad", "text", None), ("sube_id", "Şube", "select", "subeler"),
                                                      ("telefon", "Telefon", "text", None), ("eposta", "E-Posta", "text", None), ("aktif", "Aktif", "bool", None)]),
    "sirketler": (models.SigortaSirketi, "Sigorta Şirketleri", [("kod", "Kod", "text", None), ("ad", "Şirket Adı", "text", None), ("acente_kodu", "Acente Kodu", "text", None),
                                                                 ("telefon", "Telefon", "text", None), ("web", "Web / Portal", "text", None), ("aktif", "Aktif", "bool", None)]),
    "tali-acenteler": (models.TaliAcente, "Tali Acenteler", [("kod", "Kod", "text", None), ("ad", "Ad", "text", None), ("komisyon_orani", "Komisyon %", "number", None),
                                                             ("telefon", "Telefon", "text", None), ("aktif", "Aktif", "bool", None)]),
    "branslar": (models.AnaBrans, "Ana Branşlar", [("kod", "Kod", "text", None), ("ad", "Branş Adı", "text", None), ("arac_gerekli", "Plaka Zorunlu", "bool", None), ("sira", "Sıra", "number", None)]),
    "ara-branslar": (models.AraBrans, "Ara Branşlar", [("ana_brans_id", "Ana Branş", "select", "branslar"), ("kod", "Kod", "text", None), ("ad", "Ara Branş Adı", "text", None)]),
}


@router.get("")
def ana(request: Request, k: models.Kullanici = Depends(giris_gerekli)):
    return RedirectResponse("/tanimlar/sirketler", status_code=303)


@router.get("/kullanicilar")
def kullanicilar(request: Request, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    liste = list(db.scalars(select(models.Kullanici).order_by(models.Kullanici.kullanici_adi)))
    return render(request, "tanimlar/kullanicilar.html", liste=liste, TANIMLAR=TANIMLAR, **secenekler(db))


@router.post("/kullanicilar")
def kullanici_kaydet(request: Request, id: str = Form(""), kullanici_adi: str = Form(...), ad_soyad: str = Form(...), rol: str = Form("temsilci"), eposta: str = Form(""),
                     temsilci_id: str = Form(""), sifre: str = Form(""), aktif: str = Form("1"), k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    u = db.get(models.Kullanici, tam(id)) if id else None
    if u is None:
        if not sifre:
            flash(request, "Yeni kullanıcı için parola girin.", "hata")
            return RedirectResponse("/tanimlar/kullanicilar", status_code=303)
        u = models.Kullanici(sifre_hash=sifre_ozetle(sifre))
        db.add(u)
    elif sifre:
        u.sifre_hash = sifre_ozetle(sifre)
    u.kullanici_adi = kullanici_adi.strip().lower()
    u.ad_soyad, u.rol, u.eposta, u.temsilci_id = ad_soyad.strip(), rol if rol in ("admin", "yonetici", "temsilci") else "temsilci", bos(eposta), tam(temsilci_id)
    u.aktif = aktif == "1" or u.id == k.id
    logla(db, k, "Kullanıcı kaydedildi", "tanim", None, u.kullanici_adi)
    db.commit()
    flash(request, "Kullanıcı kaydedildi.")
    return RedirectResponse("/tanimlar/kullanicilar", status_code=303)


@router.get("/parametreler")
def parametreler(request: Request, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    liste = list(db.scalars(select(models.Parametre).order_by(models.Parametre.ad)))
    return render(request, "tanimlar/parametreler.html", liste=liste, TANIMLAR=TANIMLAR)


@router.post("/parametreler")
async def parametre_kaydet(request: Request, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    f = await request.form()
    for ad, deger in f.items():
        if ad.startswith("p__"):
            p = db.get(models.Parametre, ad[3:])
            if p:
                p.deger = deger
    yeni_ad = (f.get("yeni_ad") or "").strip()
    if yeni_ad:
        db.merge(models.Parametre(ad=yeni_ad, deger=f.get("yeni_deger") or "", aciklama=f.get("yeni_aciklama") or ""))
    logla(db, k, "Parametreler güncellendi", "tanim")
    db.commit()
    flash(request, "Parametreler kaydedildi.")
    return RedirectResponse("/tanimlar/parametreler", status_code=303)


@router.get("/loglar")
def loglar(request: Request, q: str = "", sayfa: int = 1, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    s = select(models.IslemLog)
    if q:
        like = f"%{q}%"
        s = s.where((models.IslemLog.islem.like(like)) | (models.IslemLog.aciklama.like(like)) | (models.IslemLog.kullanici.like(like)))
    sonuc = sayfala(db, s.order_by(models.IslemLog.id.desc()), sayfa, 100)
    return render(request, "tanimlar/loglar.html", **sonuc, q=q, TANIMLAR=TANIMLAR)


@router.get("/{tur}")
def liste(request: Request, tur: str, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    if tur not in TANIMLAR:
        return RedirectResponse("/tanimlar/sirketler", status_code=303)
    model, baslik, alanlar = TANIMLAR[tur]
    kayitlar = list(db.scalars(select(model).order_by(model.id)))
    return render(request, "tanimlar/liste.html", tur=tur, baslik=baslik, alanlar=alanlar, kayitlar=kayitlar, TANIMLAR=TANIMLAR, **secenekler(db))


@router.post("/{tur}")
async def kaydet(request: Request, tur: str, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    if tur not in TANIMLAR:
        return RedirectResponse("/tanimlar", status_code=303)
    model, baslik, alanlar = TANIMLAR[tur]
    f = dict(await request.form())
    nesne = db.get(model, tam(f.get("id"))) if f.get("id") else None
    if nesne is None:
        nesne = model()
        db.add(nesne)
    for ad, _, tip, _ in alanlar:
        v = f.get(ad)
        if tip == "bool":
            setattr(nesne, ad, v == "1")
        elif tip == "number":
            setattr(nesne, ad, para(v) if ad == "komisyon_orani" else tam(v, 0))
        elif tip == "select":
            setattr(nesne, ad, tam(v))
        else:
            setattr(nesne, ad, bos(v))
    try:
        db.flush()
    except Exception as e:  # tekil kod ihlali vb.
        db.rollback()
        flash(request, f"Kayıt yapılamadı: {str(e)[:120]}", "hata")
        return RedirectResponse(f"/tanimlar/{tur}", status_code=303)
    logla(db, k, f"{baslik}: kayıt", "tanim", nesne.id)
    db.commit()
    flash(request, "Kaydedildi.")
    return RedirectResponse(f"/tanimlar/{tur}", status_code=303)


@router.post("/{tur}/{id_}/sil")
def sil(request: Request, tur: str, id_: int, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    if tur not in TANIMLAR:
        return RedirectResponse("/tanimlar", status_code=303)
    model, baslik, _ = TANIMLAR[tur]
    nesne = bul(db, model, id_, baslik)
    try:
        db.delete(nesne)
        db.commit()
        flash(request, "Silindi.")
    except Exception:
        db.rollback()
        if hasattr(nesne, "aktif"):
            nesne.aktif = False
            db.commit()
            flash(request, "Kayıt kullanımda olduğu için silinemedi, pasife alındı.", "bilgi")
        else:
            flash(request, "Kayıt kullanımda olduğu için silinemedi.", "hata")
    return RedirectResponse(f"/tanimlar/{tur}", status_code=303)
