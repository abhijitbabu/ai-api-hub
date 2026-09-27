from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.database import get_db
from app.models import Connector
from app.providers.base import FilePart
from app.services.invocation import invoke_connector
from app.services.schema_utils import parse_json

router = APIRouter()


def _connector(db: Session, slug: str) -> Connector:
    connector = db.scalar(select(Connector).where(Connector.slug == slug))
    if not connector:
        raise HTTPException(404, detail={"success": False, "data": {}, "error": {"type": "not_found", "message": "Unknown API"}})
    return connector


def _check_key(request: Request, connector: Connector) -> None:
    incoming = request.headers.get("x-api-key") or request.headers.get("authorization", "")
    if incoming.lower().startswith("bearer "):
        incoming = incoming[7:]
    if incoming != connector.api_key:
        raise HTTPException(
            401,
            detail={"success": False, "data": {}, "error": {"type": "unauthorized", "message": "Invalid or missing API key"}},
        )


@router.api_route("/api/{slug}", methods=["POST"])
async def invoke(slug: str, request: Request, db: Session = Depends(get_db)):
    connector = _connector(db, slug)
    _check_key(request, connector)
    params = parse_json(connector.input_params, [])
    content_type = request.headers.get("content-type", "")
    values: dict = {}
    uploads: dict[str, FilePart] = {}

    if "multipart/form-data" in content_type:
        form = await request.form()
        for param in params:
            name = param["name"]
            field_type = param.get("type", "text")
            item = form.get(name)
            if field_type in {"image", "file"}:
                if isinstance(item, UploadFile) and item.filename:
                    data = await item.read()
                    uploads[name] = FilePart(
                        filename=item.filename,
                        content_type=item.content_type or "application/octet-stream",
                        data=data,
                        kind="image" if field_type == "image" or (item.content_type or "").startswith("image/") else "file",
                    )
            elif item is not None and not isinstance(item, UploadFile):
                values[name] = item
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            raise HTTPException(
                400,
                detail={"success": False, "data": {}, "error": {"type": "validation_error", "message": "JSON body must be an object"}},
            )
        values = body

    result = await invoke_connector(db, connector, values, uploads)
    status = int(result.pop("_status", 200 if result["success"] else 400))
    return JSONResponse(status_code=status, content=result)
