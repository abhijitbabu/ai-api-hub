import json
from time import perf_counter

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Connector, ModelCache, UsageLog, utcnow
from app.providers import get_provider
from app.providers.base import FilePart
from app.services.prompt import build_user_payload, wrap_system_prompt
from app.services.schema_utils import coerce_value, extract_json, parse_json, validate_against_schema

MAX_BYTES = settings.max_upload_mb * 1024 * 1024


class InvokeError(Exception):
    def __init__(self, message: str, error_type: str = "invoke_error", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code


def connector_stats(db: Session, connector_id: int) -> dict:
    rows = db.scalars(select(UsageLog).where(UsageLog.connector_id == connector_id)).all()
    total = len(rows)
    success = sum(1 for r in rows if r.success)
    failed = total - success
    times = [r.response_time_ms for r in rows if r.response_time_ms]
    tokens = [r.total_tokens for r in rows if r.total_tokens]
    costs = [r.estimated_cost for r in rows if r.estimated_cost is not None]
    first_used = min((r.created_at for r in rows), default=None)
    last_used = max((r.created_at for r in rows), default=None)
    return {
        "total_requests": total,
        "successful_requests": success,
        "failed_requests": failed,
        "avg_response_ms": int(sum(times) / len(times)) if times else None,
        "total_tokens": sum(tokens) if tokens else 0,
        "estimated_cost": round(sum(costs), 6) if costs else 0,
        "first_used": first_used,
        "last_used": last_used,
    }


def dashboard_rows(db: Session) -> list[dict]:
    connectors = db.scalars(select(Connector).order_by(Connector.created_at.desc())).all()
    counts = dict(
        db.execute(
            select(UsageLog.connector_id, func.count(UsageLog.id)).group_by(UsageLog.connector_id)
        ).all()
    )
    last_used = dict(
        db.execute(
            select(UsageLog.connector_id, func.max(UsageLog.created_at)).group_by(UsageLog.connector_id)
        ).all()
    )
    rows = []
    for c in connectors:
        params = parse_json(c.input_params, [])
        input_summary = ", ".join(sorted({p.get("type", "text") for p in params})) or "—"
        rows.append(
            {
                "connector": c,
                "input_summary": input_summary,
                "requests": counts.get(c.id, 0),
                "last_used": last_used.get(c.id),
            }
        )
    return rows


def collect_inputs(params: list[dict], form_or_json: dict, uploads: dict[str, FilePart]) -> tuple[dict, list[FilePart]]:
    values = {}
    files: list[FilePart] = []
    for param in params:
        name = param.get("name")
        if not name:
            continue
        field_type = param.get("type", "text")
        required = bool(param.get("required"))
        if field_type in {"image", "file"}:
            part = uploads.get(name)
            if required and not part:
                raise InvokeError(f"Missing required file field '{name}'", "validation_error")
            if part:
                if len(part.data) > MAX_BYTES:
                    raise InvokeError(
                        f"File '{name}' exceeds {settings.max_upload_mb} MB limit",
                        "payload_too_large",
                        413,
                    )
                files.append(part)
            continue
        raw = form_or_json.get(name, param.get("default"))
        if isinstance(raw, str) and raw.strip() == "":
            raw = None
        if raw is None and required:
            raise InvokeError(f"Missing required field '{name}'", "validation_error")
        if raw is None:
            continue
        try:
            values[name] = coerce_value(field_type, raw)
        except Exception as exc:
            raise InvokeError(f"Invalid value for '{name}': {exc}", "validation_error") from exc
    return values, files


async def invoke_connector(
    db: Session,
    connector: Connector,
    form_or_json: dict,
    uploads: dict[str, FilePart],
) -> dict:
    started = perf_counter()
    params = parse_json(connector.input_params, [])
    schema = parse_json(connector.output_schema, {})
    log = UsageLog(
        connector_id=connector.id,
        provider=connector.provider,
        model=connector.model,
        success=False,
    )
    try:
        if not connector.is_active:
            raise InvokeError("This API is disabled", "disabled", 403)
        provider = get_provider(connector.provider)
        if not provider.is_configured():
            raise InvokeError(
                f"Provider '{connector.provider}' is not configured on the server",
                "provider_not_configured",
                503,
            )
        values, files = collect_inputs(params, form_or_json, uploads)
        user_text = build_user_payload(params, values, files)
        system = wrap_system_prompt(connector.system_prompt, schema)
        result = await provider.generate(
            model=connector.model,
            system_prompt=system,
            user_text=user_text,
            files=files,
            json_mode=True,
        )
        parsed = extract_json(result.text)
        data = validate_against_schema(parsed, schema)
        elapsed = int((perf_counter() - started) * 1000)
        log.success = True
        log.response_time_ms = elapsed
        log.input_tokens = result.input_tokens
        log.output_tokens = result.output_tokens
        log.total_tokens = result.total_tokens
        log.estimated_cost = result.estimated_cost
        db.add(log)
        db.commit()
        return {
            "success": True,
            "data": data,
            "error": None,
            "meta": {
                "response_time_ms": elapsed,
                "provider": connector.provider,
                "model": connector.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "estimated_cost": result.estimated_cost,
            },
        }
    except InvokeError as exc:
        elapsed = int((perf_counter() - started) * 1000)
        log.response_time_ms = elapsed
        log.error_type = exc.error_type
        log.error_message = exc.message
        _safe_add_log(db, log)
        return {
            "success": False,
            "data": {},
            "error": {"type": exc.error_type, "message": exc.message},
            "meta": {"response_time_ms": elapsed, "provider": connector.provider, "model": connector.model},
            "_status": exc.status_code,
        }
    except httpx.TimeoutException:
        elapsed = int((perf_counter() - started) * 1000)
        log.response_time_ms = elapsed
        log.error_type = "timeout"
        log.error_message = "The AI provider timed out"
        _safe_add_log(db, log)
        return {
            "success": False,
            "data": {},
            "error": {"type": "timeout", "message": "The AI provider timed out"},
            "meta": {"response_time_ms": elapsed},
            "_status": 504,
        }
    except httpx.HTTPStatusError as exc:
        elapsed = int((perf_counter() - started) * 1000)
        detail = _safe_http_detail(exc)
        log.response_time_ms = elapsed
        log.error_type = "provider_error"
        log.error_message = detail
        _safe_add_log(db, log)
        return {
            "success": False,
            "data": {},
            "error": {"type": "provider_error", "message": detail},
            "meta": {"response_time_ms": elapsed},
            "_status": 502,
        }
    except Exception as exc:
        elapsed = int((perf_counter() - started) * 1000)
        log.response_time_ms = elapsed
        log.error_type = "internal_error"
        log.error_message = str(exc)
        _safe_add_log(db, log)
        return {
            "success": False,
            "data": {},
            "error": {"type": "internal_error", "message": "Request failed. Check logs for details."},
            "meta": {"response_time_ms": elapsed},
            "_status": 500,
        }


def _safe_add_log(db: Session, log: UsageLog) -> None:
    try:
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()


def _safe_http_detail(exc: httpx.HTTPStatusError) -> str:
    try:
        payload = exc.response.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if payload.get("message"):
                return str(payload["message"])
    except Exception:
        pass
    return f"Provider returned HTTP {exc.response.status_code}"


async def refresh_models(db: Session, provider_id: str) -> list[str]:
    provider = get_provider(provider_id)
    models = await provider.list_models()
    cache = db.scalar(select(ModelCache).where(ModelCache.provider == provider_id))
    payload = json.dumps(models)
    if cache:
        cache.models_json = payload
        cache.updated_at = utcnow()
    else:
        db.add(ModelCache(provider=provider_id, models_json=payload, updated_at=utcnow()))
    db.commit()
    return models


def cached_models(db: Session, provider_id: str) -> list[str]:
    cache = db.scalar(select(ModelCache).where(ModelCache.provider == provider_id))
    if cache:
        return parse_json(cache.models_json, [])
    provider = get_provider(provider_id)
    return list(getattr(provider, "default_models", []) or [])
