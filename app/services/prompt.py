import json
from typing import Any

from app.providers.base import FilePart


def build_user_payload(params: list[dict], values: dict[str, Any], files: list[FilePart]) -> str:
    lines = ["Submitted input:"]
    for param in params:
        name = param["name"]
        field_type = param.get("type", "text")
        if field_type in {"image", "file"}:
            continue
        if name in values and values[name] is not None:
            lines.append(f"- {name}: {json.dumps(values[name], ensure_ascii=False)}")
    if files:
        lines.append("Attached files:")
        for part in files:
            lines.append(f"- {part.filename} ({part.content_type}, {len(part.data)} bytes)")
    return "\n".join(lines)


def wrap_system_prompt(instructions: str, output_schema: dict) -> str:
    schema_text = json.dumps(output_schema, indent=2)
    return (
        f"{instructions.strip()}\n\n"
        "You must return only valid JSON. Do not wrap it in markdown.\n"
        "The JSON object must match this structure (use these keys):\n"
        f"{schema_text}"
    )
