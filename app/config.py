from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    data_dir: Path = Path("./data")
    gemini_chat_model: str = "gemini-3.8-flash"
    gemini_embed_model: str = "gemini-embedding-001"

    # Retrieval tuning
    embed_dimensions: int = 3072
    search_limit: int = 10
    # gemini-embedding-001 has a high similarity floor: across a survey of 11
    # queries, unrelated assets still scored 0.55-0.61 while genuine matches sat at
    # 0.61-0.73. 0.63 is the empirical split. It is a soft filter tuned on a small
    # corpus, so ranking, not the cutoff, is what search quality rests on.
    min_similarity: float = 0.63
    max_upload_bytes: int = 10 * 1024 * 1024

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
