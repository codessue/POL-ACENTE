"""Dosya ekleri - PoliSoft 'Dosya Yönetimi' / userfiles karşılığı."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..auth import giris_gerekli
from ..config import settings
from ..database import get_db
from ..utils import flash, logla
from .ortak import bos, bul

router = APIRouter(prefix="/dosyalar", tags=["dosyalar"])
IZINLI = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv", ".zip"}
MAKS_BOYUT = 20 * 1024 * 1024
GERI = {"hesap": "/hesaplar/{id}?sekme=dosyalar", "police": "/policeler/{id}", "talep": "/talepler/{id}", "potansiyel": "/potansiyel"}


@router.post("/yukle")
async def yukle(request: Request, yer: str = Form(...), yer_id: int = Form(...), tur: str = Form("Diğer"), aciklama: str = Form(""),
                dosya: UploadFile = File(...), k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    if yer not in GERI:
        raise HTTPException(400, "Geçersiz konum")
    geri = GERI[yer].format(id=yer_id)
    uz = Path(dosya.filename or "").suffix.lower()
    if uz not in IZINLI:
        flash(request, f"'{uz}' uzantısına izin verilmiyor.", "hata")
        return RedirectResponse(geri, status_code=303)
    icerik = await dosya.read()
    if len(icerik) > MAKS_BOYUT:
        flash(request, "Dosya 20 MB sınırını aşıyor.", "hata")
        return RedirectResponse(geri, status_code=303)
    sistem_ad = f"{uuid.uuid4().hex}{uz}"
    hedef = settings.UPLOAD_DIR / yer
    hedef.mkdir(parents=True, exist_ok=True)
    (hedef / sistem_ad).write_bytes(icerik)
    d = models.Dosya(yer=yer, yer_id=yer_id, orijinal_ad=dosya.filename, sistem_ad=sistem_ad, boyut=len(icerik), uzanti=uz, tur=tur,
                     aciklama=bos(aciklama), kullanici=k.kullanici_adi)
    db.add(d)
    logla(db, k, "Dosya yüklendi", yer, yer_id, dosya.filename)
    db.commit()
    flash(request, "Dosya yüklendi.")
    return RedirectResponse(geri, status_code=303)


@router.get("/{did}")
def indir(did: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    d = bul(db, models.Dosya, did, "Dosya")
    yol = settings.UPLOAD_DIR / d.yer / d.sistem_ad
    if not yol.exists():
        raise HTTPException(404, "Dosya diskte bulunamadı")
    return FileResponse(str(yol), filename=d.orijinal_ad)


@router.post("/{did}/sil")
def sil(request: Request, did: int, k: models.Kullanici = Depends(giris_gerekli), db: Session = Depends(get_db)):
    d = bul(db, models.Dosya, did, "Dosya")
    geri = GERI.get(d.yer, "/").format(id=d.yer_id)
    yol = settings.UPLOAD_DIR / d.yer / d.sistem_ad
    if yol.exists():
        yol.unlink()
    db.delete(d)
    logla(db, k, "Dosya silindi", d.yer, d.yer_id, d.orijinal_ad)
    db.commit()
    return RedirectResponse(geri, status_code=303)
