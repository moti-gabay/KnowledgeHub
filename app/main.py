from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    yield


app = FastAPI(title="KnowledgeHub", lifespan=lifespan)

settings.ensure_dirs()
app.mount("/files", StaticFiles(directory=settings.uploads_dir), name="files")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse("static/index.html")
