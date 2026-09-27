import base64

import httpx

from app.config import settings
from app.providers.base import FilePart, ProviderResult


class GeminiProvider:
    id = "gemini"
    label = "Google Gemini"
    default_models = [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key)

    async def list_models(self) -> list[str]:
        if not self.is_configured():
            return list(self.default_models)
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.get(url, params={"key": settings.gemini_api_key})
            response.raise_for_status()
            payload = response.json()
        names = []
        for item in payload.get("models", []):
            name = item.get("name", "")
            methods = item.get("supportedGenerationMethods") or []
            if "generateContent" in methods:
                names.append(name.replace("models/", ""))
        return sorted(set(names)) or list(self.default_models)

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_text: str,
        files: list[FilePart],
        json_mode: bool = True,
    ) -> ProviderResult:
        parts: list[dict] = [{"text": user_text}]
        for part in files:
            mime = part.content_type or "application/octet-stream"
            parts.append(
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(part.data).decode("ascii"),
                    }
                }
            )
        body: dict = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.2},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        model_id = model.replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
            if response.status_code >= 400 and json_mode:
                body["generationConfig"].pop("responseMimeType", None)
                response = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
            response.raise_for_status()
            payload = response.json()

        candidates = payload.get("candidates") or []
        text = ""
        if candidates:
            cparts = candidates[0].get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in cparts)
        usage = payload.get("usageMetadata") or {}
        in_tok = usage.get("promptTokenCount")
        out_tok = usage.get("candidatesTokenCount")
        total = usage.get("totalTokenCount")
        cost = None
        if in_tok is not None or out_tok is not None:
            cost = ((in_tok or 0) / 1_000_000) * 0.10 + ((out_tok or 0) / 1_000_000) * 0.40
        return ProviderResult(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=total,
            estimated_cost=cost,
            raw=payload,
        )
