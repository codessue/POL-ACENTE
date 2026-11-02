"""Mesaj gönderim servisi.

PoliSoft çok sayıda ticari SMS sağlayıcısına (SMS Makinesi, İletişim Makinesi, Hermes, LeadInPlus...)
sabit kodla bağlıdır. Burada sağlayıcı soyutlanmıştır:

* ``log``      : hiçbir yere göndermez, sadece veritabanına yazar (varsayılan, geliştirme için)
* ``smtp``     : e-postaları SMTP ile gönderir
* ``http_sms`` : SMS'i basit bir JSON HTTP uç noktasına POST eder (kendi sağlayıcınıza uyarlayın)
"""
from __future__ import annotations

import json
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..utils import tl, tr_tarih


def sablon_doldur(metin: str, hesap: Optional[models.Hesap] = None, police: Optional[models.Police] = None,
                  acente: str = "") -> str:
    degerler = {
        "unvan": hesap.unvan if hesap else "",
        "police_no": police.police_no if police else "",
        "bitis": tr_tarih(police.bitis_tarihi) if police else "",
        "baslama": tr_tarih(police.baslama_tarihi) if police else "",
        "plaka": (police.plaka or "") if police else "",
        "brut": tl(police.brut_prim) if police else "",
        "sirket": police.sirket.ad if police and police.sirket else "",
        "brans": police.ana_brans.ad if police and police.ana_brans else "",
        "acente": acente or settings.APP_NAME,
    }
    try:
        return metin.format(**degerler)
    except (KeyError, IndexError, ValueError):
        return metin


def _smtp_gonder(alici: str, konu: str, icerik: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = alici
    msg["Subject"] = konu or settings.APP_NAME
    msg.set_content(icerik)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
        s.starttls(context=ctx)
        if settings.SMTP_USER:
            s.login(settings.SMTP_USER, settings.SMTP_PASS)
        s.send_message(msg)


def _http_sms_gonder(alici: str, icerik: str) -> None:
    veri = json.dumps({"to": alici, "message": icerik}).encode("utf-8")
    req = urllib.request.Request(settings.SMS_HTTP_URL, data=veri, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {settings.SMS_HTTP_TOKEN}"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 - kullanıcı tanımlı uç nokta
        if r.status >= 300:
            raise RuntimeError(f"HTTP {r.status}")


def gonder(db: Session, kanal: str, alici: str, icerik: str, konu: str = "", hesap: Optional[models.Hesap] = None,
           police: Optional[models.Police] = None, kullanici: str = "") -> models.Mesaj:
    """Mesajı loglar ve yapılandırılmış sağlayıcıyla göndermeyi dener."""
    m = models.Mesaj(hesap_id=hesap.id if hesap else None, police_id=police.id if police else None, kanal=kanal,
                     alici=alici, konu=konu, icerik=icerik, kullanici=kullanici)
    db.add(m)
    try:
        saglayici = settings.MESAJ_SAGLAYICI
        if saglayici == "log":
            m.durum = "Gönderildi"
            m.hata = "log sağlayıcısı: gerçek gönderim yapılmadı"
        elif kanal == "E-Posta" and saglayici in ("smtp", "http_sms") and settings.SMTP_HOST:
            _smtp_gonder(alici, konu, icerik)
            m.durum = "Gönderildi"
        elif kanal in ("SMS", "WhatsApp") and saglayici == "http_sms" and settings.SMS_HTTP_URL:
            _http_sms_gonder(alici, icerik)
            m.durum = "Gönderildi"
        else:
            m.durum = "Hata"
            m.hata = f"'{kanal}' kanalı için sağlayıcı yapılandırılmamış"
    except Exception as e:  # pragma: no cover - dış servis
        m.durum = "Hata"
        m.hata = str(e)[:300]
    db.flush()
    return m
