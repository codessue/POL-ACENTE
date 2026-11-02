"""OpenAcente - FastAPI uygulama girişi."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import __version__, models  # noqa: F401 - modeller Base'e kaydolsun
from .auth import GirisGerekli
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import (ajanda, api, auth_router, dashboard, dosyalar, hesaplar, mesajlar, policeler, potansiyel,
                      raporlar, tahsilat, talepler, tanimlar, yenileme)
from .templating import render

from contextlib import asynccontextmanager


@asynccontextmanager
async def _yasam(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    from .seed import ilk_kurulum
    with SessionLocal() as db:
        ilk_kurulum(db, demo=settings.DEMO_VERI)
    yield


app = FastAPI(title=settings.APP_NAME, version=__version__, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json", lifespan=_yasam)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=settings.SESSION_SURE_SN, same_site="lax")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

for r in (auth_router, dashboard, hesaplar, policeler, yenileme, potansiyel, tahsilat, ajanda, talepler, mesajlar,
          raporlar, tanimlar, dosyalar, api):
    app.include_router(r.router)


@app.exception_handler(GirisGerekli)
async def _giris_yonlendir(request: Request, exc: GirisGerekli):
    sonraki = request.url.path
    return RedirectResponse(f"/login?sonraki={sonraki}", status_code=303)


@app.exception_handler(404)
async def _bulunamadi(request: Request, exc):
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Bulunamadı"}, status_code=404)
    return render(request, "hata.html", status_code=404, kod=404, mesaj="Aradığınız sayfa bulunamadı.")

