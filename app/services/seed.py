import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Connector, new_api_key
from app.services.schema_utils import slugify


CARD_SCANNER_PROMPT = """You are a business card extraction system.
Extract the person's name, company, designation, phone, email and website from the supplied image.
If a field is not present, return an empty string.
Return only valid JSON matching the configured output structure."""

ARTICLE_WRITER_PROMPT = """You are a professional article writer.
Write a structured article using the submitted topic, optional keywords, word count, and tone.
Return only valid JSON matching the configured output structure."""


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Connector.id).limit(1)):
        return

    card = Connector(
        slug="card-scanner",
        name="Card Scanner",
        description="Extract structured contact details from a business card image.",
        provider="gemini",
        model="gemini-2.0-flash",
        system_prompt=CARD_SCANNER_PROMPT,
        input_params=json.dumps(
            [
                {
                    "name": "image",
                    "type": "image",
                    "required": True,
                    "description": "Photo or scan of a business card",
                }
            ]
        ),
        output_schema=json.dumps(
            {
                "name": "string",
                "company": "string",
                "designation": "string",
                "phone": "string",
                "email": "string",
                "website": "string",
            }
        ),
        api_key=new_api_key(),
        is_active=True,
    )
    article = Connector(
        slug="article-writer",
        name="Article Writer",
        description="Generate a structured article from a topic and writing parameters.",
        provider="groq",
        model="llama-3.1-8b-instant",
        system_prompt=ARTICLE_WRITER_PROMPT,
        input_params=json.dumps(
            [
                {"name": "topic", "type": "text", "required": True, "description": "Article topic"},
                {"name": "keywords", "type": "text", "required": False, "description": "Comma-separated keywords"},
                {"name": "word_count", "type": "number", "required": False, "description": "Target word count", "default": 600},
                {
                    "name": "options",
                    "type": "json",
                    "required": False,
                    "description": 'Extra options, e.g. {"tone":"professional"}',
                    "default": {"tone": "professional"},
                },
            ]
        ),
        output_schema=json.dumps(
            {
                "title": "string",
                "summary": "string",
                "article": "string",
                "keywords": "array",
            }
        ),
        api_key=new_api_key(),
        is_active=True,
    )
    db.add_all([card, article])
    db.commit()


def unique_slug(db: Session, name: str, existing_id: int | None = None) -> str:
    base = slugify(name)
    slug = base
    n = 2
    while True:
        found = db.scalar(select(Connector).where(Connector.slug == slug))
        if not found or found.id == existing_id:
            return slug
        slug = f"{base}-{n}"
        n += 1
