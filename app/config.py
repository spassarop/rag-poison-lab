"""Configuration management using pydantic-settings and python-dotenv."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    llm_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="LLM_MODEL")
    judge_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="JUDGE_MODEL")
    # JUDGE_MODELS: comma-separated PANEL of judges from DIFFERENT model families. A single
    # model at temperature 0 gives identical votes (no real diversity), so the panel is how
    # we get independent opinions. Empty → falls back to [judge_model].
    judge_models: str = Field(default="", alias="JUDGE_MODELS")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    # Generation temperature. Default 0.0 = greedy/deterministic, so repeated
    # measurements are reproducible. Raise it only to study output variance.
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    # Embedding & Retrieval
    embed_model: str = Field(default="paraphrase-multilingual-MiniLM-L12-v2", alias="EMBED_MODEL")
    top_k: int = Field(default=6, alias="TOP_K")

    # ChromaDB
    chroma_path: str = Field(default="http://localhost:8001", alias="CHROMA_PATH")
    chroma_collection: str = Field(default="cocina_kb", alias="CHROMA_COLLECTION")

    # Chunking
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP")

    # Attack Testing
    canary_url: str = Field(
        default="http://login-update.cocinacloud.test/login",
        alias="CANARY_URL"
    )

    # Defense Controls
    # DEFENSE_INGESTION: "off" or a comma-separated set of {signatures, veritensor, anomaly}
    #   e.g. "signatures,anomaly". Signatures catch overt+stealth; anomaly catches
    #   the non-fluent GASLITE passage; neither catches fluent plausible injections.
    defense_ingestion: str = Field(default="off", alias="DEFENSE_INGESTION")
    defense_spotlighting: str = Field(default="off", alias="DEFENSE_SPOTLIGHTING")
    defense_output: str = Field(default="off", alias="DEFENSE_OUTPUT")
    # Runtime semantic output guard: LLM judge with a generic safety rubric mitigates
    # knowledge corruption (false facts with no URL). Adds an LLM call per answer.
    defense_semantic_output: str = Field(default="off", alias="DEFENSE_SEMANTIC_OUTPUT")
    # Retrieval-time access control: customer role only sees public chunks.
    defense_retrieval_filter: str = Field(default="off", alias="DEFENSE_RETRIEVAL_FILTER")

    def judge_models_list(self) -> list:
        """The judge panel: a list of Ollama model tags. Empty JUDGE_MODELS → single judge."""
        raw = (self.judge_models or "").strip()
        if raw:
            return [m.strip() for m in raw.split(",") if m.strip()]
        return [self.judge_model]

    def ingestion_controls(self) -> set:
        """Parse DEFENSE_INGESTION into a set of active controls (empty if off)."""
        raw = (self.defense_ingestion or "").strip().lower()
        if not raw or raw == "off":
            return set()
        return {c.strip() for c in raw.split(",") if c.strip() and c.strip() != "off"}

    # Ignore unknown env vars so a partial deploy (new .env, older code, or vice
    # versa) degrades gracefully instead of crashing at startup.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
