from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FilePart:
    filename: str
    content_type: str
    data: bytes
    kind: str  # image | file


@dataclass
class ProviderResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None
    raw: dict = field(default_factory=dict)


class AIProvider(Protocol):
    id: str
    label: str

    def is_configured(self) -> bool: ...

    async def list_models(self) -> list[str]: ...

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_text: str,
        files: list[FilePart],
        json_mode: bool = True,
    ) -> ProviderResult: ...
