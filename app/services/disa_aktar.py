"""Excel / CSV dışa aktarım ve poliçe içe aktarım."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..utils import para, tarih


def excel_bytes(baslik: str, kolonlar: Sequence[str], satirlar: Iterable[Sequence]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = baslik[:30]
    ws.append(list(kolonlar))
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
    for r in satirlar:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in r])
    for i, k in enumerate(kolonlar, 1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, min(40, len(str(k)) + 4))
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def csv_bytes(kolonlar: Sequence[str], satirlar: Iterable[Sequence]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(kolonlar)
    for r in satirlar:
        w.writerow(["" if v is None else v for v in r])
    return ("﻿" + buf.getvalue()).encode("utf-8")


POLICE_ICE_AKTAR_KOLONLAR = [
    "hes_kod", "unvan", "tc_no", "vergi_no", "gsm", "sirket_kod", "ana_brans_kod", "police_no", "zeyl_no",
    "yenileme_no", "tanzim_tarihi", "baslama_tarihi", "bitis_tarihi", "brut_prim", "net_prim", "komisyon",
    "taksit_sayisi", "plaka", "temsilci_kod",
]


def _satirlari_oku(dosya_adi: str, icerik: bytes) -> list[dict]:
    if dosya_adi.lower().endswith((".xlsx", ".xlsm")):
        wb = load_workbook(io.BytesIO(icerik), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        bas = [str(h or "").strip().lower() for h in rows[0]]
        return [dict(zip(bas, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]
    metin = icerik.decode("utf-8-sig", errors="replace")
    ornek = metin[:2048]
    ayrac = ";" if ornek.count(";") >= ornek.count(",") else ","
    return [{k.strip().lower(): v for k, v in r.items()} for r in csv.DictReader(io.StringIO(metin), delimiter=ayrac)]


def police_ice_aktar(db: Session, dosya_adi: str, icerik: bytes, kullanici: str) -> dict:
    """CSV/XLSX'ten poliçe yükler; hesap kartı yoksa açar. Sonuç: {eklenen, atlanan, hatalar}."""
    sirketler = {s.kod.upper(): s for s in db.scalars(select(models.SigortaSirketi)) if s.kod}
    branslar = {b.kod.upper(): b for b in db.scalars(select(models.AnaBrans))}
    temsilciler = {t.kod.upper(): t for t in db.scalars(select(models.Temsilci)) if t.kod}
    sonuc = {"eklenen": 0, "atlanan": 0, "hatalar": []}
    for i, r in enumerate(_satirlari_oku(dosya_adi, icerik), start=2):
        try:
            sirket = sirketler.get(str(r.get("sirket_kod") or "").upper())
            brans = branslar.get(str(r.get("ana_brans_kod") or "").upper())
            if not sirket or not brans:
                raise ValueError("Şirket kodu veya branş kodu tanımsız")
            pno = str(r.get("police_no") or "").strip()
            if not pno:
                raise ValueError("Poliçe no boş")
            zeyl = int(r.get("zeyl_no") or 0)
            yen = int(r.get("yenileme_no") or 0)
            var = db.scalar(select(models.Police).where(models.Police.sirket_id == sirket.id, models.Police.police_no == pno,
                                                          models.Police.zeyl_no == zeyl, models.Police.yenileme_no == yen))
            if var:
                sonuc["atlanan"] += 1
                continue
            hesap = None
            hk = str(r.get("hes_kod") or "").strip()
            tc = str(r.get("tc_no") or "").strip() or None
            vn = str(r.get("vergi_no") or "").strip() or None
            if hk:
                hesap = db.scalar(select(models.Hesap).where(models.Hesap.hes_kod == hk))
            if hesap is None and tc:
                hesap = db.scalar(select(models.Hesap).where(models.Hesap.tc_no == tc))
            if hesap is None and vn:
                hesap = db.scalar(select(models.Hesap).where(models.Hesap.vergi_no == vn))
            if hesap is None:
                unvan = str(r.get("unvan") or "").strip()
                if not unvan:
                    raise ValueError("Hesap bulunamadı ve ünvan boş")
                hesap = models.Hesap(hes_kod=hk or yeni_hes_kod(db), unvan=unvan, tc_no=tc, vergi_no=vn,
                                     tip="Kurumsal" if vn and not tc else "Bireysel", olusturan=kullanici)
                gsm = str(r.get("gsm") or "").strip()
                if gsm:
                    hesap.telefonlar.append(models.HesapTelefon(tip="GSM", numara=gsm))
                db.add(hesap)
                db.flush()
            tanzim = tarih(str(r.get("tanzim_tarihi") or "")) if not isinstance(r.get("tanzim_tarihi"), date) else r.get("tanzim_tarihi")
            bas = tarih(str(r.get("baslama_tarihi") or "")) if not isinstance(r.get("baslama_tarihi"), date) else r.get("baslama_tarihi")
            bit = tarih(str(r.get("bitis_tarihi") or "")) if not isinstance(r.get("bitis_tarihi"), date) else r.get("bitis_tarihi")
            if not (bas and bit):
                raise ValueError("Başlama/bitiş tarihi okunamadı")
            temsilci = temsilciler.get(str(r.get("temsilci_kod") or "").upper())
            p = models.Police(hesap_id=hesap.id, sirket_id=sirket.id, ana_brans_id=brans.id, police_no=pno, zeyl_no=zeyl,
                              yenileme_no=yen, tanzim_tarihi=tanzim or bas, baslama_tarihi=bas, bitis_tarihi=bit,
                              brut_prim=para(r.get("brut_prim")), net_prim=para(r.get("net_prim")),
                              komisyon=para(r.get("komisyon")), taksit_sayisi=int(r.get("taksit_sayisi") or 1),
                              plaka=(str(r.get("plaka") or "").upper().replace(" ", "") or None),
                              temsilci_id=temsilci.id if temsilci else hesap.temsilci_id, kaynak="İçe Aktarım",
                              olusturan=kullanici, durum="Aktif" if bit >= date.today() else "Süresi Doldu")
            db.add(p)
            sonuc["eklenen"] += 1
        except Exception as e:  # satır bazlı hata toplanır, işlem devam eder
            sonuc["hatalar"].append(f"Satır {i}: {e}")
    db.commit()
    return sonuc


def yeni_hes_kod(db: Session) -> str:
    son = db.scalar(select(models.Hesap.id).order_by(models.Hesap.id.desc()))
    return f"H{(son or 0) + 1:06d}"
