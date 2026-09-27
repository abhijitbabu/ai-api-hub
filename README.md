# AI API Hub

Production-style **Universal AI API Connector**: one dashboard to define reusable AI APIs (prompt, inputs, output schema, provider/model). Each connector becomes a real `POST` endpoint with generated docs, a test console, and persistent usage logs.

This matches the *Universal AI API Connector & API Hub* examination assignment.

## What you get

- Admin dashboard of connectors (no login, as required for evaluation)
- Create / edit / disable / delete connectors
- Dynamic input fields: text, number, boolean, image, file, JSON
- Structured JSON output with light schema normalization
- Provider adapters: **Groq**, **Google Gemini**, plus optional **OpenAI** and **OpenRouter**
- Model dropdown cache + **Refresh models**
- Generated docs (`/docs` and `/docs/{slug}`) with cURL examples
- Test playground per connector
- Persistent SQLite/Postgres usage stats (tokens, latency, errors, estimated cost)
- Seeded demos: **Card Scanner** (Gemini, image) and **Article Writer** (Groq, text)

Provider API keys stay on the server. Generated endpoints use a per-connector `X-API-Key`.

## Run locally

```powershell
cd C:\Users\abhij\ai-api-hub
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add at least two keys (required for the two demo connectors):

```
GROQ_API_KEY=...
GEMINI_API_KEY=...
```

Free keys: [Groq Console](https://console.groq.com/) and [Google AI Studio](https://aistudio.google.com/apikey).

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

- Dashboard: `/`
- API docs index: `/docs`
- Card scanner: `POST /api/card-scanner`
- Article writer: `POST /api/article-writer`

Copy the connector API key from the connector detail page.

### Example calls

Text:

```powershell
curl -X POST http://127.0.0.1:8000/api/article-writer `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"topic\":\"Digital marketing\",\"word_count\":400}"
```

Image:

```powershell
curl -X POST http://127.0.0.1:8000/api/card-scanner `
  -H "X-API-Key: YOUR_KEY" `
  -F "image=@card.jpg"
```

## Architecture

```
Browser / external app
        │
        ▼
 FastAPI  (app/main.py)
   ├─ HTML dashboard (app/routes/ui.py + templates)
   ├─ POST /api/{slug} (app/routes/public.py)
   ├─ Provider adapters (app/providers/)
   └─ SQLAlchemy models + usage_logs (app/models.py)
```

Adding a provider means implementing `list_models` + `generate` and registering it in `app/providers/__init__.py`. The rest of the hub does not change.

## Hosting (required for submission)

The assignment rejects localhost-only work. Deploy anywhere that runs Docker or a Python web process:

1. Push this repo to GitHub (`https://github.com/abhijitbabu/ai-api-hub`).
2. Create a web service on [Render](https://render.com/) or [Railway](https://railway.app/).
3. Set env vars: `GROQ_API_KEY`, `GEMINI_API_KEY`, `APP_BASE_URL` (your public URL), `SECRET_KEY`.
4. Prefer Postgres (`DATABASE_URL`) so logs survive restarts. SQLite is fine for local demos only. The Docker build (`Dockerfile`) already installs the Postgres driver via `requirements-prod.txt` — if you deploy without Docker (e.g. a buildpack-based host that just runs `pip install -r requirements.txt`), install from `requirements-prod.txt` instead so the Postgres driver is included. Don't add `psycopg2-binary` to your local Windows/Mac dev environment — it's Linux-only in this project because prebuilt wheels aren't always available for the newest Python versions on Windows.
5. After deploy, open the live dashboard, test both seeded APIs, and put these in your submission:
   - Live app URL
   - `https://YOURHOST/docs`
   - `POST https://YOURHOST/api/card-scanner`
   - `POST https://YOURHOST/api/article-writer`

## Security notes

- Never commit `.env`.
- Do not paste provider keys into docs, screenshots, or GitHub.
- Rotate a connector key from its detail page if it leaks.

## Best first change

On the **Article Writer** connector, tighten the prompt or output schema (for example add an `outline` array). That is a one-file product change through the UI, or edit `app/services/seed.py` if you want it baked into a fresh database.
