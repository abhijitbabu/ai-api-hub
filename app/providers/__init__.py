from app.providers.gemini import GeminiProvider
from app.providers.openai_compat import groq_provider, openai_provider, openrouter_provider

PROVIDERS = {
    "groq": groq_provider(),
    "gemini": GeminiProvider(),
    "openai": openai_provider(),
    "openrouter": openrouter_provider(),
}


def get_provider(provider_id: str):
    provider = PROVIDERS.get(provider_id)
    if provider is None:
        raise KeyError(f"Unknown provider: {provider_id}")
    return provider


def provider_choices() -> list[dict]:
    return [
        {
            "id": p.id,
            "label": p.label,
            "configured": p.is_configured(),
        }
        for p in PROVIDERS.values()
    ]
