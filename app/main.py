from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Connector
from app.routes.admin import router as admin_router
from app.routes.public import router as public_router
from app.routes.ui import router as ui_router
from app.services.seed import seed_if_empty

TEMPLATES = Path(__file__).resolve().parent / "templates"
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title=settings.app_name, docs_url="/openapi", redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES))
app.state.templates = templates


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.exception_handler(StarletteHTTPException)
async def http_exc(request: Request, exc: StarletteHTTPException):
    api_path = request.url.path.startswith("/api/") or request.url.path.startswith("/admin/api")
    detail = exc.detail
    if api_path:
        if isinstance(detail, dict) and "success" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "data": {}, "error": {"type": "http_error", "message": str(detail)}},
        )
    message = detail if isinstance(detail, str) else "Request failed"
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{message}</p>", status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    if request.url.path.startswith("/api/") or request.url.path.startswith("/admin/api"):
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": {}, "error": {"type": "internal_error", "message": "Unexpected server error"}},
        )
    return HTMLResponse("<h1>500</h1><p>Unexpected server error</p>", status_code=500)


@app.get("/health")
def health():
    return {"ok": True, "app": settings.app_name}


@app.get("/sitemap-apis")
def sitemap_apis():
    db = SessionLocal()
    try:
        slugs = db.scalars(select(Connector.slug).where(Connector.is_active.is_(True))).all()
        return {"endpoints": [f"/api/{slug}" for slug in slugs]}
    finally:
        db.close()


app.include_router(ui_router)
app.include_router(admin_router)
app.include_router(public_router)
