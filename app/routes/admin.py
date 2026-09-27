from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.providers import PROVIDERS, provider_choices
from app.services.invocation import cached_models, refresh_models

router = APIRouter(prefix="/admin/api")


class RefreshBody(BaseModel):
    provider: str


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    return {
        "providers": [
            {**item, "models": cached_models(db, item["id"])}
            for item in provider_choices()
        ]
    }


@router.post("/models/refresh")
async def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    if body.provider not in PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    try:
        models = await refresh_models(db, body.provider)
    except Exception as exc:
        raise HTTPException(502, f"Could not refresh models: {exc}") from exc
    return {"provider": body.provider, "models": models}
