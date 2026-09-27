# What was broken and what was fixed

This project was ~95% built by Cursor before credits ran out. The architecture,
templates, providers, and routes were all already in place. Three real bugs were
stopping it from actually running. All three are fixed in this copy.

## 1. Crash on "Refresh models" (`app/services/invocation.py`)

`refresh_models()` called `json.dumps(...)` but the file never imported `json`.
Any click on "Refresh models" in the admin UI raised `NameError: name 'json' is
not defined`.

**Fix:** added `import json` at the top of the file.

## 2. Every HTML page returned 500 (`app/routes/ui.py`)

The shared `tpl()` helper called:

```python
templates.TemplateResponse(name, {...context...})
```

This is the **old** Starlette calling convention. The Starlette version that gets
installed today (pulled in transitively by an unpinned `fastapi>=0.115`) has
fully removed that signature. Passing `(name, context)` positionally meant
`request` silently received the template name string and `name` received the
context dict — which made Jinja's internal template cache try to hash a dict and
crash with `TypeError: unhashable type: 'dict'`.

This broke literally every page: dashboard, docs, connector detail, edit, test
console, stats — all of it.

**Fix:** call it the current way: `TemplateResponse(request, name, context)`.

## 3. File/image uploads always reported "missing" (`app/routes/public.py` and `app/routes/ui.py`)

Both files did:

```python
from fastapi import UploadFile
...
isinstance(item, UploadFile)
```

On the currently-installed FastAPI/Starlette combo, `fastapi.UploadFile` is a
**subclass** of `starlette.datastructures.UploadFile`. The object actually
returned by `request.form()` is the *base* Starlette class, not the FastAPI
subclass — so `isinstance(item, fastapi.UploadFile)` was always `False`, even
for a perfectly valid uploaded file.

The practical effect: **the Card Scanner connector (the required image → vision
demo) could never receive an image**, either through the real
`POST /api/card-scanner` endpoint or through the in-browser Test Console. Every
request came back `"Missing required file field 'image'"` no matter what was
uploaded. This would have failed live evaluation.

**Fix:** import `UploadFile` from `starlette.datastructures` instead of
`fastapi` in both files, so the `isinstance` check matches the real runtime type.

## Also done

- Pinned exact working versions in `requirements.txt` (previously only had loose
  `>=` bounds, which is what let an incompatible newer Starlette get pulled in
  and cause bug #2/#3 in the first place). Re-verified with a fully clean
  `python -m venv` + `pip install -r requirements.txt` + full page/API pass.
- Confirmed end-to-end with real HTTP calls (not just imports):
  - All pages render (200)
  - 401 on missing/invalid API key
  - 400 `validation_error` on missing required fields
  - 503 `provider_not_configured` when no provider key is set
  - 502 `provider_error` when a request reaches the real provider with a bad key
    (proves the image *did* get sent, once bug #3 was fixed)
  - Model refresh endpoint works without crashing
  - Created a brand-new third connector purely through the web UI form and
    confirmed it got a working endpoint, API key, and docs page automatically

## What's left for you to do

1. Get free API keys:
   - Groq: https://console.groq.com/
   - Gemini: https://aistudio.google.com/apikey
2. Put them in `.env` (locally) or as environment variables (on your host).
3. Deploy per the README (Render/Railway, Docker or Procfile — both included).
4. Once deployed, open the dashboard, run the Test Console on both seeded
   connectors (Card Scanner with a real business card image, Article Writer
   with a topic) to get real sample responses for your submission.
5. For the submission write-up: the architecture section in `README.md`
   already covers this; you can reuse it almost verbatim.
