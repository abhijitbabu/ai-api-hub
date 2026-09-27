from app.providers.base import FilePart, ProviderResult
from app.config import settings
import base64
import httpx


class OpenAICompatibleProvider:
    def __init__(
        self,
        provider_id: str,
        label: str,
        base_url: str,
        api_key: str,
        extra_headers: dict | None = None,
        default_models: list[str] | None = None,
        input_cost_per_m: float = 0.0,
        output_cost_per_m: float = 0.0,
    ):
        self.id = provider_id
        self.label = label
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.extra_headers = extra_headers or {}
        self.default_models = default_models or []
        self.input_cost_per_m = input_cost_per_m
        self.output_cost_per_m = output_cost_per_m

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        return headers

    async def list_models(self) -> list[str]:
        if not self.is_configured():
            return list(self.default_models)
        url = f"{self.base_url}/models"
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            payload = response.json()
        ids = [item.get("id") for item in payload.get("data", []) if item.get("id")]
        return sorted(set(ids)) or list(self.default_models)

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_text: str,
        files: list[FilePart],
        json_mode: bool = True,
    ) -> ProviderResult:
        content: list[dict] = [{"type": "text", "text": user_text}]
        for part in files:
            b64 = base64.b64encode(part.data).decode("ascii")
            mime = part.content_type or "application/octet-stream"
            if part.kind == "image" or mime.startswith("image/"):
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    }
                )
            else:
                content.append(
                    {
                        "type": "text",
                        "text": f"[Attached file: {part.filename} ({mime}), {len(part.data)} bytes. Contents not inlined.]",
                    }
                )

        body: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content if files else user_text},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.post(url, headers=self._headers(), json=body)
            if response.status_code >= 400 and json_mode:
                body.pop("response_format", None)
                response = await client.post(url, headers=self._headers(), json=body)
            response.raise_for_status()
            payload = response.json()

        text = payload["choices"][0]["message"]["content"] or ""
        usage = payload.get("usage") or {}
        in_tok = usage.get("prompt_tokens")
        out_tok = usage.get("completion_tokens")
        total = usage.get("total_tokens")
        if total is None and in_tok is not None and out_tok is not None:
            total = in_tok + out_tok
        cost = None
        if in_tok is not None or out_tok is not None:
            cost = ((in_tok or 0) / 1_000_000) * self.input_cost_per_m + (
                (out_tok or 0) / 1_000_000
            ) * self.output_cost_per_m
        return ProviderResult(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=total,
            estimated_cost=cost,
            raw=payload,
        )


def groq_provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        provider_id="groq",
        label="Groq",
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        default_models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct"],
        input_cost_per_m=0.59,
        output_cost_per_m=0.79,
    )


def openai_provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        provider_id="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key=settings.openai_api_key,
        default_models=["gpt-4o-mini", "gpt-4o"],
        input_cost_per_m=0.15,
        output_cost_per_m=0.60,
    )


def openrouter_provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        provider_id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        extra_headers={"HTTP-Referer": settings.app_base_url, "X-Title": settings.app_name},
        default_models=["openai/gpt-4o-mini", "google/gemini-2.0-flash-exp:free"],
        input_cost_per_m=0.15,
        output_cost_per_m=0.60,
    )
