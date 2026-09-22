# KnowledgeHub – Project Plan (Junior Take-Home, ~5h)

## Context
Take-home assignment (see `Junior Home Assignment.pdf`): a Knowledge Management System where users upload text/image files, an AI service generates searchable metadata on upload, and a "smart search" finds assets by meaning ("black hair" → images with black hair + text files mentioning it). Must be on GitHub, Dockerized, deployed online. No auth/security/scale. Interview will probe technical decisions. README must include a section on AI tools used during development.

Decisions confirmed with user: **Gemini** for vision + text + embeddings, **Render** for deployment. Frontend: minimal HTML/JS + Tailwind served by FastAPI (single container, single process, no second port — Streamlit would need its own process and can't serve the API).


---

## 1. High-level Architecture

```
Browser (index.html + app.js, Tailwind CDN)
   │  multipart upload / GET /api/search?q=
   ▼
FastAPI (uvicorn, one process, one container)
   ├── routers/assets.py   → upload, list, get one
   ├── routers/search.py   → semantic search
   ├── services/storage.py → save file to DATA_DIR/uploads/
   ├── services/ai.py      → Gemini: describe image / describe text / embed
   ├── services/vectorstore.py → Chroma (PersistentClient, DATA_DIR/chroma/)
   └── db.py + models.py   → SQLite via SQLAlchemy 2.0 (DATA_DIR/app.db)
   
Static: /static/* (UI), /files/* (uploaded assets, served by StaticFiles)
```

Two stores, clear roles:
- **SQLite** = source of truth for asset records (filename, kind, description, tags, text content).
- **Chroma** = one vector per asset (id = asset id) used only for similarity lookup. Search hits are joined back to SQLite by id.

---

## 2. Core Flows

### Upload flow (synchronous, ~2–6s)
1. `POST /api/upload` (multipart, field `file`).
2. Validate extension whitelist: `.txt .md` → `kind="text"`, `.png .jpg .jpeg .webp .gif` → `kind="image"`. Else 400.
3. `storage.save(file)` → writes to `DATA_DIR/uploads/{uuid}{ext}`, returns path.
4. Generate metadata via Gemini (`services/ai.py`):
   - image: send bytes as `types.Part.from_bytes(...)` + prompt → JSON `{description, tags[]}` (structured output via `response_schema`).
   - text: read content (truncate to ~8k chars), same prompt shape → same JSON.
5. Build embed text: `f"{description}\nTags: {', '.join(tags)}"` (+ first ~2k chars of content for text files).
6. `ai.embed(text, task_type="RETRIEVAL_DOCUMENT")` → vector.
7. Insert `Asset` row in SQLite; `chroma.upsert(id, embedding, metadata={"kind": kind})`.
8. Return the asset JSON. If Gemini fails → still save the asset, set `description="(metadata generation failed)"`, `tags=[]`, skip vector upsert, return 201 with a `metadata_ok=false` flag. Never lose the upload.

### Search flow
1. `GET /api/search?q=black+hair&limit=10`.
2. `ai.embed(q, task_type="RETRIEVAL_QUERY")`.
3. `chroma.query(query_embeddings=[vec], n_results=limit)` (collection created with `hnsw:space=cosine`).
4. Filter by distance threshold (start at `< 0.55`, tune with the two spec queries), fetch matching `Asset` rows from SQLite, return ordered list with `score = 1 - distance`.
5. Frontend renders results as cards: image thumbnail or text snippet, description, tags, score.

Key nuance for interview: cross-modal search works because **both images and text are reduced to a natural-language description before embedding** — the vector space is text-only (not CLIP). "black hair" matches an image because Gemini wrote "a woman with long black hair" in its description.

---

## 3. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API | `fastapi`, `uvicorn[standard]`, `python-multipart` | Async, typed, auto docs at `/docs` for demo |
| Config | `pydantic-settings` | `.env` → typed settings, one place for model names |
| DB | `sqlalchemy` 2.0 + SQLite | Zero infra, `create_all()` on startup, no Alembic |
| AI | `google-genai` (`from google import genai`) | One SDK for vision, text, embeddings; free tier |
| Models | `gemini-2.5-flash` (vision + text), `gemini-embedding-001` (768 dims via `output_dimensionality`) | Cheapest multimodal; check https://ai.google.dev/gemini-api/docs/models for current names; both in env vars |
| Vectors | `chromadb` (`PersistentClient`) | Persistent, cosine, upsert by id; we pass our own embeddings so Chroma's default ONNX model is never downloaded |
| Frontend | Static `index.html` + vanilla JS + Tailwind CDN | No build step, same origin, no CORS |
| Container | `python:3.12-slim` | Small, standard |
| Deploy | Render Web Service (Docker runtime) | Free tier, Dockerfile auto-detected |

Pin versions in `requirements.txt`.

---

## 4. Database Schema

**SQLite `assets`** (SQLAlchemy model `Asset`):

| column | type | notes |
|---|---|---|
| id | TEXT PK | `uuid4().hex` |
| kind | TEXT | `"text"` \| `"image"` |
| original_name | TEXT | as uploaded |
| stored_name | TEXT | `{id}{ext}`; URL = `/files/{stored_name}` |
| mime_type | TEXT | |
| size_bytes | INTEGER | |
| description | TEXT | AI-generated |
| tags | TEXT (JSON array) | AI-generated, lowercase |
| text_content | TEXT nullable | full text for text files (shown in detail view) |
| metadata_ok | BOOLEAN | false if AI step failed |
| created_at | DATETIME | UTC |

**Chroma collection `assets`** (cosine): `ids=[asset.id]`, `embeddings=[vec]`, `documents=[embed_text]`, `metadatas=[{"kind": kind}]`.

No FTS table, no chunks table, no users.

---

## 5. Folder Structure

```
KnowledgeHub/
├── app/
│   ├── __init__.py
│   ├── main.py            # app factory, lifespan(init_db), mounts /static + /files, includes routers
│   ├── config.py          # Settings: GEMINI_API_KEY, DATA_DIR, GEMINI_CHAT_MODEL, GEMINI_EMBED_MODEL
│   ├── db.py              # engine, SessionLocal, Base, init_db(), get_db dependency
│   ├── models.py          # Asset ORM
│   ├── schemas.py         # AssetOut, SearchHit, AssetMetadata (pydantic, reused as Gemini response_schema)
│   ├── services/
│   │   ├── ai.py          # describe_image(), describe_text(), embed()
│   │   ├── storage.py     # save_upload(), detect_kind()
│   │   └── vectorstore.py # get_collection(), upsert(), query()
│   └── routers/
│       ├── assets.py      # POST /api/upload, GET /api/assets, GET /api/assets/{id}
│       └── search.py      # GET /api/search
├── static/
│   ├── index.html
│   └── app.js
├── data/                  # gitignored; uploads/, chroma/, app.db
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 6. Implementation Plan (~5h)

**Phase 0 – Scaffold (20 min)**
- `git init`, venv, `requirements.txt`, `.env.example`, `.gitignore` (`data/`, `.env`, `__pycache__`).
- `config.py`, `main.py` with `GET /health`. Run `uvicorn app.main:app --reload`.
- ✅ verify: `curl localhost:8000/health` → `{"ok":true}`.

**Phase 1 – Storage + DB + upload/list/get (40 min)**
- `db.py`, `models.py`, `storage.py`, `routers/assets.py` (no AI yet; description empty).
- Mount `StaticFiles(directory=DATA_DIR/uploads)` at `/files`.
- ✅ verify: `curl -F file=@photo.jpg localhost:8000/api/upload` → JSON with id; `GET /api/assets` lists it; `/files/{stored_name}` serves the image.

**Phase 2 – Gemini metadata (50 min)**
- `schemas.AssetMetadata(description: str, tags: list[str])`.
- `ai.py`: single `_generate(parts) -> AssetMetadata` using `generate_content(... config=GenerateContentConfig(response_mime_type="application/json", response_schema=AssetMetadata))`; `describe_image(bytes, mime)` and `describe_text(str)` wrap it.
- Prompt: "Describe this {image|text} in 1–2 sentences for a search index. Then give 5–10 short lowercase tags (nouns/attributes: objects, people, colors, hair color, clothing, document type, topics)."
- Wire into upload with try/except → `metadata_ok`.
- ✅ verify: upload a portrait photo → tags include hair color; upload a scanned-letter photo → tags include "document"; upload a `.txt` about haircuts → description mentions hair.

**Phase 3 – Embeddings + Chroma + search (45 min)**
- `ai.embed(text, task_type)` → `client.models.embed_content(model=..., contents=text, config=EmbedContentConfig(task_type=task_type, output_dimensionality=768)).embeddings[0].values`.
- `vectorstore.py`: `PersistentClient(path=DATA_DIR/chroma)`, `get_or_create_collection("assets", metadata={"hnsw:space":"cosine"})`, `upsert`, `query`.
- Upsert on upload; `routers/search.py`.
- ✅ verify: `GET /api/search?q=black hair` returns the portrait + hair text file, not the letter; `q=document` returns the letter photo + any text about documents. Tune threshold.

**Phase 4 – Frontend (50 min)**
- `index.html`: header, upload form (file input + button + spinner), search box, results grid. Tailwind CDN.
- `app.js`: `uploadFile()`, `search(q)`, `loadAll()` on page load, `renderCards(items)`. Card: `<img>` for images, first 200 chars for text, description, tag chips, score badge. Click → open `/files/{stored_name}` in new tab (text files render inline in browser).
- ✅ verify: full flow in browser; empty search shows all assets.

**Phase 5 – Docker + Render deploy (45 min)**
- `Dockerfile`: `python:3.12-slim`, `pip install -r requirements.txt`, copy `app/ static/`, `ENV DATA_DIR=/app/data`, `CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- `.dockerignore`: `data/ .env .git venv`.
- ✅ verify local: `docker build -t kh . && docker run -p 8000:8000 --env-file .env kh`.
- Push to GitHub. Render → New Web Service → Docker runtime → env var `GEMINI_API_KEY`. Render injects `PORT`.
- ✅ verify: public URL works end-to-end.

**Phase 6 – README + polish (30 min)**
- README: what it does, architecture diagram (the ASCII above), run locally, run with Docker, env vars, **AI tools used** section, **Design decisions** section (pull from §7), **Known limitations** (§8).
- Optional if time: `seed/` folder with 2 images + 1 text file, processed on startup when DB is empty, so the Render demo isn't blank after a restart.

Total ≈ 4h40, ~20 min buffer.

---

## 7. Interview: Decisions to Be Ready to Explain

1. **Why embeddings instead of keyword/FTS?** Spec says "reference it" — "haircut tips" text should match "black hair". Keyword misses synonyms; embeddings capture meaning. Trade-off: no exact-match guarantee; hybrid (FTS5 + vectors, reciprocal rank fusion) is the next step.
2. **How does text ↔ image search work?** Both become text descriptions first; one text embedding space. Not CLIP. Limitation: search quality bounded by description quality → prompt asks for concrete attributes (colors, hair, objects, document types).
3. **Why one embedding per asset, no chunking?** Assets are small; search returns whole assets, not passages. Chunking is a RAG concern; this is retrieval-only.
4. **Why SQLite + Chroma (two stores)?** Relational data and vectors have different query patterns. SQLite is truth; Chroma is a derived index that can be rebuilt from SQLite (worth adding a `reindex` script if asked). Alternative at this scale: store vectors in SQLite and do numpy cosine — honest to say Chroma is slightly over-provisioned for ~100 assets but gives proper ANN + persistence for free.
5. **Why Gemini for everything?** One SDK, one key, native multimodal, native structured output, free tier. Model names live in env vars so swapping is a config change.
6. **Why synchronous processing on upload?** 2–6s is acceptable UX with a spinner; a queue/BackgroundTasks + `status` column would be the next step and adds polling to the UI. Simpler is correct for this scope.
7. **Failure handling:** upload never fails because of the AI; `metadata_ok=false` is visible in the UI. Text truncated to 8k chars before the LLM.
8. **Why FastAPI + static HTML, not Streamlit/React?** Single container, single process, API is testable via `/docs`, no build step.
9. **Why local FS + SQLite?** Spec says no scale. Path to production: S3 for files, Postgres + pgvector (one store instead of two), worker queue for AI, presigned URLs.
10. **Cosine threshold:** explain it's empirically tuned; scores are shown in the UI so relevance is transparent.
11. **Cost/latency:** ~1 vision call + 1 embed per upload, 1 embed per search. Negligible.

---

## 8. Risks & Simplifications

| Risk | Mitigation / decision |
|---|---|
| Render free tier: ephemeral disk → uploads, SQLite, Chroma wiped on redeploy/restart | Accept; state in README. Optional seed-on-startup so demo isn't empty. Render spins down after 15 min idle → first request ~30–60s; note in README. |
| `chromadb` is a heavy dependency (slow Docker build, big image) | Pass own embeddings so no ONNX download. If build pain: fall back to numpy cosine over vectors stored in SQLite (~30 lines). |
| Gemini model name changes / quota errors | Model names in env; catch exceptions → `metadata_ok=false`. Free tier has RPM limits; fine for demo. |
| Large text files | Truncate to 8k chars for the LLM, 2k for the embed text. |
| Unsupported / malicious files | Extension + `content_type` whitelist, 10 MB size cap. Nothing more. |
| Threshold too strict/loose | Show scores in UI; always return top-k with threshold as a soft filter. |
| SQLite/Chroma drift | Write SQLite first, then Chroma; on failure keep the row with `metadata_ok=false`. |

**Deliberately skipped:** auth, delete/edit, pagination, hybrid search, chunking, background jobs, tests beyond a smoke test, migrations, CORS config (same origin).

---

## Verification (end-to-end)
1. Local: upload portrait, scanned letter, haircut `.txt` → `/api/search?q=black hair` returns portrait + txt; `q=document` returns letter.
2. `docker build` + `docker run` reproduces step 1.
3. Render URL reproduces step 1; README instructions work from a clean clone.
