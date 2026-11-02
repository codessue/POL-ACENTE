"""Ajanda: görev, randevu, ziyaret, hatırlatma - PoliSoft 'frmAjanda' / 'jobs' / 'randevu' karşılığı."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import giris_gerekli
from ..database import get_db
from ..templating import render
from ..utils import flash, logla, tam, tarih
from .ortak import bos, bul, secenekler

router = APIRouter(prefix="/ajanda", tags=["ajanda"])
TIPLER = ["Görev", "Arama", "Randevu", "Ziyaret", "Hatırlatma"]


@router.get("")
def liste(request: Request, gorunum: str = "hafta", baslangic: str = "", atanan_id: Optional[int] = None, durum: str = "Açık",
          k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    G = models.Gorev
    bas = tarih(baslangic) or date.today()
    if gorunum == "hafta":
        bas = bas - timedelta(days=bas.weekday())
        son = bas + timedelta(days=6)
    elif gorunum == "gun":
        son = bas
    else:
        bas = bas.replace(day=1)
        son = (bas.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    s = select(G).options(selectinload(G.hesap), selectinload(G.atanan))
    if gorunum != "tum":
        s = s.where(G.tarih.between(bas, son))
    if durum:
        s = s.where(G.durum == durum)
    if atanan_id:
        s = s.where(G.atanan_id == atanan_id)
    kayitlar = list(db.scalars(s.order_by(G.tarih, G.saat)))
    gunler = []
    g = bas
    while g <= son and gorunum in ("hafta", "gun"):
        gunler.append((g, [x for x in kayitlar if x.tarih == g]))
        g += timedelta(days=1)
    geciken = list(db.scalars(select(G).where(G.durum == "Açık", G.tarih < date.today()).order_by(G.tarih))) if gorunum != "tum" else []
    return render(request, "ajanda/liste.html", kayitlar=kayitlar, gunler=gunler, gorunum=gorunum, bas=bas, son=son, atanan_id=atanan_id, durum=durum,
                  onceki=(bas - timedelta(days=7 if gorunum == "hafta" else 1 if gorunum == "gun" else 31)),
                  sonraki=(son + timedelta(days=1)), geciken=geciken, TIPLER=TIPLER, **secenekler(db))


@router.get("/yeni")
def yeni_form(request: Request, hesap_id: Optional[int] = None, police_id: Optional[int] = None, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    hesap = db.get(models.Hesap, hesap_id) if hesap_id else None
    return render(request, "ajanda/form.html", g=None, hesap=hesap, police_id=police_id, TIPLER=TIPLER, **secenekler(db))


@router.post("/yeni")
async def yeni(request: Request, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    f = dict(await request.form())
    g = models.Gorev(baslik=(f.get("baslik") or "").strip(), aciklama=bos(f.get("aciklama")), tip=f.get("tip") or "Görev",
                     tarih=tarih(f.get("tarih")) or date.today(), saat=bos(f.get("saat")), hesap_id=tam(f.get("hesap_id")),
                     police_id=tam(f.get("police_id")), atanan_id=tam(f.get("atanan_id")) or k.id, olusturan=k.kullanici_adi)
    if not g.baslik:
        flash(request, "Başlık zorunludur.", "hata")
        return RedirectResponse("/ajanda/yeni", status_code=303)
    db.add(g)
    db.flush()
    logla(db, k, f"{g.tip} oluşturuldu", "hesap" if g.hesap_id else "ajanda", g.hesap_id or g.id, g.baslik)
    db.commit()
    flash(request, "Kayıt eklendi.")
    hedef = f.get("sonraki") or (f"/hesaplar/{g.hesap_id}?sekme=gorevler" if g.hesap_id else "/ajanda")
    return RedirectResponse(hedef, status_code=303)


@router.get("/{gid}/duzenle")
def duzenle_form(request: Request, gid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    g = bul(db, models.Gorev, gid, "Görev")
    return render(request, "ajanda/form.html", g=g, hesap=g.hesap, police_id=g.police_id, TIPLER=TIPLER, **secenekler(db))


@router.post("/{gid}/duzenle")
async def duzenle(request: Request, gid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    g = bul(db, models.Gorev, gid, "Görev")
    f = dict(await request.form())
    g.baslik = (f.get("baslik") or g.baslik).strip()
    g.aciklama = bos(f.get("aciklama"))
    g.tip = f.get("tip") or g.tip
    g.tarih = tarih(f.get("tarih")) or g.tarih
    g.saat = bos(f.get("saat"))
    g.atanan_id = tam(f.get("atanan_id")) or g.atanan_id
    g.hesap_id = tam(f.get("hesap_id")) or g.hesap_id
    db.commit()
    flash(request, "Güncellendi.")
    return RedirectResponse("/ajanda", status_code=303)


@router.post("/{gid}/durum")
def durum(request: Request, gid: int, durum: str = Form(...), sonuc: str = Form(""), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    g = bul(db, models.Gorev, gid, "Görev")
    g.durum = durum if durum in ("Açık", "Tamamlandı", "İptal") else g.durum
    g.sonuc = bos(sonuc) or g.sonuc
    g.tamamlanma = datetime.now() if g.durum != "Açık" else None
    logla(db, k, f"Görev {g.durum.lower()}", "hesap" if g.hesap_id else "ajanda", g.hesap_id or g.id, g.baslik)
    db.commit()
    return RedirectResponse(request.headers.get("referer") or "/ajanda", status_code=303)


@router.post("/{gid}/sil")
def sil(request: Request, gid: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    g = bul(db, models.Gorev, gid, "Görev")
    db.delete(g)
    db.commit()
    return RedirectResponse("/ajanda", status_code=303)
