"""Mesajlar: şablonlar, tekil/toplu gönderim, hatırlatma kuralları - PoliSoft 'frmGlobalSMSDialog', 'frmSMSSablonlari', 'frmAlertTanim' karşılığı."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli, yonetici_gerekli
from ..database import get_db
from ..services import hatirlatma_servisi, mesaj_servisi
from ..templating import render
from ..utils import flash, logla, tam
from .ortak import bos, bul, parametre, sayfala, secenekler

router = APIRouter(prefix="/mesajlar", tags=["mesajlar"])
KANALLAR = ["SMS", "E-Posta", "WhatsApp"]


@router.get("")
def liste(request: Request, kanal: str = "", durum: str = "", sayfa: int = 1, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    M = models.Mesaj
    s = select(M).options(selectinload(M.hesap))
    if kanal:
        s = s.where(M.kanal == kanal)
    if durum:
        s = s.where(M.durum == durum)
    sonuc = sayfala(db, s.order_by(M.id.desc()), sayfa)
    return render(request, "mesajlar/liste.html", **sonuc, kanal=kanal, durum=durum, KANALLAR=KANALLAR)


@router.get("/sablonlar")
def sablonlar(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    liste_ = list(db.scalars(select(models.MesajSablon).order_by(models.MesajSablon.kanal, models.MesajSablon.ad)))
    kurallar = list(db.scalars(select(models.HatirlatmaKurali)))
    return render(request, "mesajlar/sablonlar.html", sablonlar=liste_, kurallar=kurallar, KANALLAR=KANALLAR, **secenekler(db))


@router.post("/sablonlar")
def sablon_kaydet(request: Request, id: str = Form(""), ad: str = Form(...), kanal: str = Form("SMS"), konu: str = Form(""), icerik: str = Form(...),
                  aktif: str = Form("1"), k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    s = db.get(models.MesajSablon, tam(id)) if id else None
    if s is None:
        s = models.MesajSablon()
        db.add(s)
    s.ad, s.kanal, s.konu, s.icerik, s.aktif = ad.strip(), kanal, bos(konu), icerik, aktif == "1"
    db.commit()
    flash(request, "Şablon kaydedildi.")
    return RedirectResponse("/mesajlar/sablonlar", status_code=303)


@router.post("/sablonlar/{sid}/sil")
def sablon_sil(request: Request, sid: int, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    s = bul(db, models.MesajSablon, sid, "Şablon")
    if db.scalar(select(models.HatirlatmaKurali.id).where(models.HatirlatmaKurali.sablon_id == sid)):
        flash(request, "Bu şablonu kullanan hatırlatma kuralı var.", "hata")
    else:
        db.delete(s)
        db.commit()
    return RedirectResponse("/mesajlar/sablonlar", status_code=303)


@router.post("/kurallar")
def kural_kaydet(request: Request, id: str = Form(""), ad: str = Form(...), gun_once: int = Form(30), kanal: str = Form("SMS"), sablon_id: int = Form(...),
                 ana_brans_id: str = Form(""), aktif: str = Form("1"), k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    r = db.get(models.HatirlatmaKurali, tam(id)) if id else None
    if r is None:
        r = models.HatirlatmaKurali()
        db.add(r)
    r.ad, r.gun_once, r.kanal, r.sablon_id, r.ana_brans_id, r.aktif = ad.strip(), gun_once, kanal, sablon_id, tam(ana_brans_id), aktif == "1"
    db.commit()
    flash(request, "Kural kaydedildi.")
    return RedirectResponse("/mesajlar/sablonlar", status_code=303)


@router.post("/kurallar/{rid}/sil")
def kural_sil(rid: int, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    r = bul(db, models.HatirlatmaKurali, rid, "Kural")
    db.delete(r)
    db.commit()
    return RedirectResponse("/mesajlar/sablonlar", status_code=303)


@router.post("/kurallari-calistir")
def kurallari_calistir(request: Request, k: models.Kullanici = Depends(yonetici_gerekli), db: Session = Depends(get_db)):
    n = hatirlatma_servisi.calistir(db, k)
    logla(db, k, "Hatırlatma kuralları çalıştırıldı", "mesaj", None, f"{n} ileti")
    db.commit()
    flash(request, f"{n} hatırlatma iletisi oluşturuldu.", "bilgi")
    return RedirectResponse("/mesajlar", status_code=303)


@router.post("/gonder")
def gonder(request: Request, hesap_id: int = Form(...), kanal: str = Form("SMS"), alici: str = Form(""), sablon_id: str = Form(""), icerik: str = Form(""),
           konu: str = Form(""), police_id: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    h = bul(db, models.Hesap, hesap_id, "Hesap")
    p = db.get(models.Police, tam(police_id)) if police_id else None
    sablon = db.get(models.MesajSablon, tam(sablon_id)) if sablon_id else None
    acente = parametre(db, "acente_unvan", "")
    metin = icerik.strip() or (sablon.icerik if sablon else "")
    if not metin:
        flash(request, "Mesaj içeriği boş.", "hata")
        return RedirectResponse(f"/hesaplar/{hesap_id}?sekme=mesajlar", status_code=303)
    metin = mesaj_servisi.sablon_doldur(metin, h, p, acente)
    konu_m = mesaj_servisi.sablon_doldur(konu or (sablon.konu if sablon else "") or "", h, p, acente)
    alici = alici.strip() or (h.eposta if kanal == "E-Posta" else h.gsm)
    if not alici:
        flash(request, "Alıcı bilgisi yok (GSM / e-posta ekleyin).", "hata")
        return RedirectResponse(f"/hesaplar/{hesap_id}?sekme=iletisim", status_code=303)
    m = mesaj_servisi.gonder(db, kanal, alici, metin, konu_m, h, p, k.kullanici_adi)
    logla(db, k, f"{kanal} gönderildi", "hesap", h.id, alici)
    db.commit()
    flash(request, f"Mesaj kaydedildi ({m.durum}).", "basari" if m.durum == "Gönderildi" else "hata")
    return RedirectResponse(f"/hesaplar/{hesap_id}?sekme=mesajlar", status_code=303)


@router.get("/toplu")
def toplu_form(request: Request, gun: int = 30, ana_brans_id: Optional[int] = None, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    """Toplu hatırlatma: bitişine N gün kalan poliçeler."""
    bugun = date.today()
    P = models.Police
    s = select(P).options(selectinload(P.hesap).selectinload(models.Hesap.telefonlar)).where(P.durum == "Aktif", P.bitis_tarihi.between(bugun, bugun + timedelta(days=gun)))
    if ana_brans_id:
        s = s.where(P.ana_brans_id == ana_brans_id)
    policeler = list(db.scalars(s.order_by(P.bitis_tarihi)))
    sablonlar = list(db.scalars(select(models.MesajSablon).where(models.MesajSablon.aktif.is_(True))))
    return render(request, "mesajlar/toplu.html", policeler=policeler, gun=gun, ana_brans_id=ana_brans_id, sablonlar=sablonlar, KANALLAR=KANALLAR, **secenekler(db))


@router.post("/toplu")
async def toplu(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = await request.form()
    kanal = f.get("kanal") or "SMS"
    sablon = db.get(models.MesajSablon, tam(f.get("sablon_id")))
    if sablon is None:
        flash(request, "Şablon seçin.", "hata")
        return RedirectResponse("/mesajlar/toplu", status_code=303)
    acente = parametre(db, "acente_unvan", "")
    gonderilen, atlanan = 0, 0
    for pid in f.getlist("police_id"):
        p = db.get(models.Police, tam(pid))
        if p is None:
            continue
        h = p.hesap
        alici = h.eposta if kanal == "E-Posta" else h.gsm
        if not alici or not h.kvkk_onay:
            atlanan += 1
            continue
        mesaj_servisi.gonder(db, kanal, alici, mesaj_servisi.sablon_doldur(sablon.icerik, h, p, acente),
                             mesaj_servisi.sablon_doldur(sablon.konu or "", h, p, acente), h, p, k.kullanici_adi)
        gonderilen += 1
    logla(db, k, "Toplu mesaj", "mesaj", None, f"{gonderilen} gönderildi, {atlanan} atlandı (KVKK/iletişim yok)")
    db.commit()
    flash(request, f"{gonderilen} ileti oluşturuldu, {atlanan} kayıt atlandı (KVKK onayı veya iletişim bilgisi yok).", "bilgi")
    return RedirectResponse("/mesajlar", status_code=303)
