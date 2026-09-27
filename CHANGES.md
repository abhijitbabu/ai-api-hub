# What was fixed in this pass

Starting point: the project from `FIXES.md` (three earlier bugs already fixed —
model refresh crash, `TemplateResponse` calling convention, and file-upload
`isinstance` check). This pass found and fixed one more **severe** bug plus two
deployment hardening gaps.

## 1. "Create API" and "Edit API" pages always crashed (500) — `app/templates/connector_form.html`

This is the single most important page in the whole assignment: it's how an
administrator "creates a new API and gives it a name and description... selects
an AI provider and model... defines the instructions/prompt... defines the
input fields... defines the expected output structure" (assignment section 3,
steps 2–6). It was completely broken:

- The `{% block scripts %}` tag was declared **twice** in a row (invalid Jinja —
  blocks can't nest inside themselves like that).
- Inside it, `FIELD_TYPES` was built as `JSON.parse('...')` with a Jinja
  fallback string containing manually backslash-escaped quotes
  (`\\"string\\"`). Jinja does not parse escaped quotes that way inside an
  expression, so the template failed to *compile* — not just render — meaning
  **every request to `/connectors/new` and `/connectors/{id}/edit` returned a
  raw HTTP 500** with a `jinja2.exceptions.TemplateSyntaxError`.
- Below that, a second, unrelated chunk of `DOMContentLoaded` JavaScript sat
  **outside of any `<script>` tag** (the first `</script>` closed too early),
  so even if the syntax error weren't fatal, that code would have rendered as
  literal visible text on the page instead of running.
- A stray leftover word ("impulse") had also gotten mixed into one of the
  helper sentences describing output-schema types.

**Fix:** replaced the whole broken block with a single, clean `<script>` tag
that sets `window.HUB_FORM` using Jinja's `|tojson` filter directly (which
already produces valid, safely-escaped JSON for embedding in HTML/JS — no
manual escaping or `JSON.parse` wrapper needed). This also turned out to be
exactly what `app/static/app.js` (already correct, already loaded by
`base.html`) was expecting all along — `app.js` was fully working code that the
broken inline script in `connector_form.html` was redundantly and incorrectly
trying to reimplement inline. Removing the broken duplicate let the good code
in `app.js` take over.

Verified end-to-end with real HTTP calls: `/connectors/new`, `/connectors/{id}/edit`,
and a full create → view → edit → test → docs → delete cycle all return 200,
with the model dropdown, dynamic input-field builder, and "Refresh models"
button working through `app.js`.

## 2. Postgres deploys would have failed at startup — `requirements.txt`

`render.yaml` already provisions a managed Postgres database and wires its
`DATABASE_URL` into the web service (the right call — Render's free-tier disks
are ephemeral, so SQLite there would violate the assignment's "statistics must
survive a restart" requirement). But nothing in `requirements.txt` could
actually *speak* to Postgres — SQLAlchemy needs a driver. The moment
`DATABASE_URL` pointed at a real `postgresql://` URL, the app would crash on
its first database call.

**Fix:** added `psycopg2-binary` to `requirements.txt`, which is what
SQLAlchemy's default `postgresql://` URL scheme resolves to. No code changes
needed — `app/database.py` already normalizes `postgres://` → `postgresql://`.

## 3. Local secrets/test data could get baked into the Docker image

There was no `.dockerignore`, so `Dockerfile`'s `COPY . .` would happily copy
a developer's local `.env` (with real provider keys!) and `data/hub.db` (with
whatever test connectors/logs had accumulated locally) straight into the
image.

**Fix:** added `.dockerignore` excluding `.env`, `data/`, `.git/`, virtualenvs,
`__pycache__`, and other local-only files, mirroring `.gitignore`.

## 4. `pip install -r requirements.txt` failed on Windows (`psycopg2-binary`)

Fix #2 above added `psycopg2-binary` straight into `requirements.txt`, which
broke local installs on Windows: that package doesn't yet ship a prebuilt
wheel for every Python version there, so pip fell back to compiling it from
source, which needs `pg_config` (part of a full PostgreSQL server install)
that isn't present in a normal dev setup — and pip aborts the *entire* batch
install when one package fails, so nothing (not even `uvicorn`) got installed.

**Fix:** moved the Postgres driver out of `requirements.txt` and into a new
`requirements-prod.txt` (`-r requirements.txt` plus `psycopg2-binary`), and
pointed `Dockerfile` at that file instead. Local development never needs a
Postgres driver at all (it uses SQLite by default), and the Docker build only
ever runs on Linux, where prebuilt wheels for `psycopg2-binary` are always
available. Re-verified with a clean `pip install -r requirements.txt` in a
fresh virtualenv — installs and boots with zero errors.

## Also cleaned up

- Removed the committed `venv/`, `.git/`, and `data/hub.db` (accumulated local
  test data) from this delivery so you start from a clean, empty database —
  the two seeded demo connectors (Card Scanner, Article Writer) will be
  created automatically on first run.
- Removed a stray `package-lock.json` (leftover from tooling; this is a pure
  Python project, not Node).
