import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import assets, search
from app.services.seeding import seed_if_empty


# Without this the app's own loggers sit at WARNING and seeding progress is
# invisible in the deployment logs.
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    threading.Thread(target=seed_if_empty, daemon=True).start()
    yield


app = FastAPI(title="KnowledgeHub", lifespan=lifespan)

settings.ensure_dirs()
app.mount("/files", StaticFiles(directory=settings.uploads_dir), name="files")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(assets.router)
app.include_router(search.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse("static/index.html")
