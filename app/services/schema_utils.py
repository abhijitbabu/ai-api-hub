import json
import re
from typing import Any


FIELD_TYPES = ("text", "number", "boolean", "image", "file", "json")


def parse_json(value: str, default: Any):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    slug = slug.strip("-")
    return slug or "api"


def extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty model response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return json.loads(fenced.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Model did not return valid JSON")


def coerce_value(field_type: str, raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if field_type == "number":
        return float(raw) if "." in str(raw) else int(raw)
    if field_type == "boolean":
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in {"1", "true", "yes", "on"}
    if field_type == "json":
        if isinstance(raw, (dict, list)):
            return raw
        return json.loads(raw)
    return str(raw)


def validate_against_schema(data: Any, schema: dict) -> dict:
    """Shallow object schema: {field: type-name}."""
    if not isinstance(schema, dict) or not schema:
        return data if isinstance(data, dict) else {"value": data}
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object matching the output schema")
    normalized = {}
    for key, type_name in schema.items():
        value = data.get(key)
        if value is None:
            normalized[key] = None
            continue
        expected = str(type_name).lower()
        if expected in {"string", "str"}:
            normalized[key] = str(value)
        elif expected in {"number", "int", "integer", "float"}:
            normalized[key] = float(value) if not isinstance(value, bool) else float(int(value))
        elif expected in {"boolean", "bool"}:
            normalized[key] = bool(value)
        elif expected in {"array", "list"}:
            if not isinstance(value, list):
                raise ValueError(f"Field '{key}' must be an array")
            normalized[key] = value
        elif expected in {"object", "dict"}:
            if not isinstance(value, dict):
                raise ValueError(f"Field '{key}' must be an object")
            normalized[key] = value
        else:
            normalized[key] = value
    return normalized
