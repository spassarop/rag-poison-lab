"""Configuration management using pydantic-settings and python-dotenv."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    llm_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="LLM_MODEL")
    judge_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="JUDGE_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    # Generation temperature. Default 0.0 = greedy/deterministic, so repeated
    # measurements are reproducible. Raise it only to study output variance.
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    # Embedding & Retrieval
    embed_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBED_MODEL")
    top_k: int = Field(default=4, alias="TOP_K")

    # ChromaDB
    chroma_path: str = Field(default="http://localhost:8001", alias="CHROMA_PATH")
    chroma_collection: str = Field(default="cocina_kb", alias="CHROMA_COLLECTION")

    # Chunking
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP")

    # Attack Testing
    canary_url: str = Field(
        default="http://secure-login-update.cocina-cloud-phish.test/login",
        alias="CANARY_URL"
    )

    # Defense Controls
    defense_ingestion: str = Field(default="off", alias="DEFENSE_INGESTION")
    defense_spotlighting: str = Field(default="off", alias="DEFENSE_SPOTLIGHTING")
    defense_output: str = Field(default="off", alias="DEFENSE_OUTPUT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
