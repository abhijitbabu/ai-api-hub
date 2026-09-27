import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.config import settings
from app.database import get_db
from app.models import Connector, UsageLog, new_api_key, utcnow
from app.providers import PROVIDERS, provider_choices
from app.providers.base import FilePart
from app.services.invocation import cached_models, connector_stats, dashboard_rows, invoke_connector
from app.services.schema_utils import FIELD_TYPES, parse_json
from app.services.seed import unique_slug

router = APIRouter()


def tpl(request: Request, name: str, **ctx):
    return request.app.state.templates.TemplateResponse(
        request,
        name,
        {
            "app_name": settings.app_name,
            "base_url": str(request.base_url).rstrip("/"),
            "providers": provider_choices(),
            "field_types": FIELD_TYPES,
            **ctx,
        },
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    return tpl(request, "dashboard.html", rows=dashboard_rows(db))


@router.get("/connectors/new", response_class=HTMLResponse)
def new_connector(request: Request, db: Session = Depends(get_db)):
    return tpl(
        request,
        "connector_form.html",
        connector=None,
        models_by_provider={pid: cached_models(db, pid) for pid in PROVIDERS},
        default_params=[{"name": "topic", "type": "text", "required": True, "description": ""}],
        default_schema='{\n  "result": "string"\n}',
    )


@router.post("/connectors")
async def create_connector(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    provider: str = Form(...),
    model: str = Form(...),
    system_prompt: str = Form(""),
    input_params: str = Form("[]"),
    output_schema: str = Form("{}"),
    is_active: str = Form("on"),
    db: Session = Depends(get_db),
):
    _validate_params_schema(input_params, output_schema)
    connector = Connector(
        slug=unique_slug(db, name),
        name=name.strip(),
        description=description.strip(),
        provider=provider,
        model=model.strip(),
        system_prompt=system_prompt,
        input_params=input_params,
        output_schema=output_schema,
        api_key=new_api_key(),
        is_active=is_active == "on",
    )
    db.add(connector)
    db.commit()
    return RedirectResponse(url=f"/connectors/{connector.id}", status_code=303)


@router.get("/connectors/{connector_id}", response_class=HTMLResponse)
def connector_detail(connector_id: int, request: Request, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    stats = connector_stats(db, connector.id)
    recent = db.scalars(
        select(UsageLog).where(UsageLog.connector_id == connector.id).order_by(UsageLog.created_at.desc()).limit(25)
    ).all()
    return tpl(
        request,
        "connector_detail.html",
        connector=connector,
        stats=stats,
        recent=recent,
        params=parse_json(connector.input_params, []),
        schema=parse_json(connector.output_schema, {}),
    )


@router.get("/connectors/{connector_id}/edit", response_class=HTMLResponse)
def edit_connector(connector_id: int, request: Request, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    return tpl(
        request,
        "connector_form.html",
        connector=connector,
        models_by_provider={pid: cached_models(db, pid) for pid in PROVIDERS},
        default_params=parse_json(connector.input_params, []),
        default_schema=json.dumps(parse_json(connector.output_schema, {}), indent=2),
    )


@router.post("/connectors/{connector_id}")
async def update_connector(
    connector_id: int,
    name: str = Form(...),
    description: str = Form(""),
    provider: str = Form(...),
    model: str = Form(...),
    system_prompt: str = Form(""),
    input_params: str = Form("[]"),
    output_schema: str = Form("{}"),
    is_active: str = Form("off"),
    db: Session = Depends(get_db),
):
    connector = _get(db, connector_id)
    _validate_params_schema(input_params, output_schema)
    connector.name = name.strip()
    connector.description = description.strip()
    connector.provider = provider
    connector.model = model.strip()
    connector.system_prompt = system_prompt
    connector.input_params = input_params
    connector.output_schema = output_schema
    connector.is_active = is_active == "on"
    connector.slug = unique_slug(db, name, existing_id=connector.id)
    connector.updated_at = utcnow()
    db.commit()
    return RedirectResponse(url=f"/connectors/{connector.id}", status_code=303)


@router.post("/connectors/{connector_id}/toggle")
def toggle_connector(connector_id: int, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    connector.is_active = not connector.is_active
    db.commit()
    return RedirectResponse(url=f"/connectors/{connector.id}", status_code=303)


@router.post("/connectors/{connector_id}/rotate-key")
def rotate_key(connector_id: int, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    connector.api_key = new_api_key()
    db.commit()
    return RedirectResponse(url=f"/connectors/{connector.id}", status_code=303)


@router.post("/connectors/{connector_id}/delete")
def delete_connector(connector_id: int, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    db.delete(connector)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/connectors/{connector_id}/test", response_class=HTMLResponse)
def test_page(connector_id: int, request: Request, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    return tpl(
        request,
        "test.html",
        connector=connector,
        params=parse_json(connector.input_params, []),
        result=None,
    )


@router.post("/connectors/{connector_id}/test", response_class=HTMLResponse)
async def run_test(connector_id: int, request: Request, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    params = parse_json(connector.input_params, [])
    form = await request.form()
    values, uploads = await _extract_from_form(form, params)
    result = await invoke_connector(db, connector, values, uploads)
    return tpl(
        request,
        "test.html",
        connector=connector,
        params=params,
        result=result,
    )


@router.get("/connectors/{connector_id}/docs", response_class=HTMLResponse)
def connector_docs(connector_id: int, request: Request, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    params = parse_json(connector.input_params, [])
    return tpl(
        request,
        "docs.html",
        connector=connector,
        params=params,
        schema=parse_json(connector.output_schema, {}),
        has_files=any(p.get("type") in {"image", "file"} for p in params),
    )


@router.get("/docs", response_class=HTMLResponse)
def docs_index(request: Request, db: Session = Depends(get_db)):
    connectors = db.scalars(select(Connector).order_by(Connector.name)).all()
    return tpl(request, "docs_index.html", connectors=connectors)


@router.get("/docs/{slug}", response_class=HTMLResponse)
def public_docs(slug: str, request: Request, db: Session = Depends(get_db)):
    connector = db.scalar(select(Connector).where(Connector.slug == slug))
    if not connector:
        raise HTTPException(404, "Unknown API")
    params = parse_json(connector.input_params, [])
    return tpl(
        request,
        "docs.html",
        connector=connector,
        params=params,
        schema=parse_json(connector.output_schema, {}),
        has_files=any(p.get("type") in {"image", "file"} for p in params),
    )


@router.get("/connectors/{connector_id}/stats", response_class=HTMLResponse)
def stats_page(connector_id: int, request: Request, db: Session = Depends(get_db)):
    connector = _get(db, connector_id)
    stats = connector_stats(db, connector.id)
    recent = db.scalars(
        select(UsageLog).where(UsageLog.connector_id == connector.id).order_by(UsageLog.created_at.desc()).limit(100)
    ).all()
    return tpl(request, "stats.html", connector=connector, stats=stats, recent=recent)


def _get(db: Session, connector_id: int) -> Connector:
    connector = db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    return connector


def _validate_params_schema(input_params: str, output_schema: str) -> None:
    params = parse_json(input_params, None)
    schema = parse_json(output_schema, None)
    if not isinstance(params, list):
        raise HTTPException(400, "Input parameters must be a JSON array")
    if not isinstance(schema, dict):
        raise HTTPException(400, "Output schema must be a JSON object")


async def _extract_from_form(form, params: list[dict]) -> tuple[dict, dict[str, FilePart]]:
    values: dict = {}
    uploads: dict[str, FilePart] = {}
    for param in params:
        name = param["name"]
        field_type = param.get("type", "text")
        item = form.get(name)
        if field_type in {"image", "file"}:
            if isinstance(item, UploadFile) and item.filename:
                data = await item.read()
                kind = "image" if field_type == "image" or (item.content_type or "").startswith("image/") else "file"
                uploads[name] = FilePart(
                    filename=item.filename,
                    content_type=item.content_type or "application/octet-stream",
                    data=data,
                    kind=kind,
                )
            continue
        if item is not None and not isinstance(item, UploadFile):
            values[name] = item
    return values, uploads
