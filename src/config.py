from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator
from typing import Optional, Dict, Literal, Any
from urllib.parse import urlparse

def _ensure_port(uri: str) -> str:
    if not uri:
        return uri
    p = urlparse(uri)
    return uri if p.port else (uri.rstrip("/") + ":19530")


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(None, alias="OPENAI_BASE_URL")
    openai_chat_model: str = Field("gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embed_model: str = Field("text-embedding-3-small", alias="OPENAI_EMBED_MODEL")

    # Milvus / Zilliz
    milvus_uri: str = Field(..., alias="MILVUS_URI")
    milvus_token: str = Field(..., alias="MILVUS_TOKEN")
    milvus_db: str = Field("default", alias="MILVUS_DB")
    milvus_collection: str = Field("diyoloji_docs", alias="MILVUS_COLLECTION")
    milvus_vector_field: str = Field("embedding", alias="MILVUS_VECTOR_FIELD")
    milvus_text_field: str = Field("text", alias="MILVUS_TEXT_FIELD")
    milvus_partition: Optional[str] = Field(None, alias="MILVUS_PARTITION")

    milvus_dim: int = Field(1536, alias="MILVUS_DIM")
    milvus_metric: str = Field("COSINE", alias="MILVUS_METRIC")
    milvus_index_type: Literal["AUTOINDEX", "HNSW", "IVF_FLAT", "IVF_SQ8", "IVF_PQ"] = "AUTOINDEX"
    milvus_hnsw_m: int = Field(8, alias="MILVUS_HNSW_M")
    milvus_hnsw_efconstruction: int = Field(64, alias="MILVUS_HNSW_EFCONSTRUCTION")
    milvus_search_ef: int = Field(128, alias="MILVUS_SEARCH_EF")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # RAG
    max_context_docs: int = Field(6, alias="MAX_CONTEXT_DOCS")
    chunk_size: int = Field(1200, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(200, alias="CHUNK_OVERLAP")
    score_threshold: float = 0.200

    # History
    history_enabled: bool = Field(True, alias="HISTORY_ENABLED")
    history_db: str = Field("./diyoloji_history.sqlite", alias="HISTORY_DB")
    history_max_turns: int = Field(6, alias="HISTORY_MAX_TURNS")
    session_ttl_days: int = Field(7, alias="SESSION_TTL_DAYS")

    # LangSmith (LangChain v2 tracing)
    langchain_tracing_v2: bool = Field(False, alias="LANGCHAIN_TRACING_V2")
    langchain_endpoint: Optional[str] = Field(None, alias="LANGCHAIN_ENDPOINT")
    langchain_api_key: Optional[str] = Field(None, alias="LANGCHAIN_API_KEY")
    langchain_project: Optional[str] = Field(None, alias="LANGCHAIN_PROJECT")

    # Selenium ve Server (opsiyonel kalemler)
    selenium_driver: str = Field("chrome", alias="SELENIUM_DRIVER")
    selenium_headless: bool = Field(True, alias="SELENIUM_HEADLESS")
    selenium_timeout: int = Field(20, alias="SELENIUM_TIMEOUT")

    server_host: str = Field("0.0.0.0", alias="SERVER_HOST")
    server_port: int = Field(8000, alias="SERVER_PORT")
    cors_origins: str = Field("*", alias="CORS_ORIGINS")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Validators (Pydantic v2 uyumlu) ---
    @field_validator("openai_base_url", mode="before")
    @classmethod
    def blank_base_url_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("milvus_metric", mode="before")
    @classmethod
    def metric_upper(cls, v: str) -> str:
        v = (v or "").upper()
        allowed = {"COSINE", "IP", "L2"}
        if v not in allowed:
            raise ValueError(f"MILVUS_METRIC must be one of {allowed}")
        return v

    @field_validator("milvus_index_type", mode="before")
    @classmethod
    def index_upper(cls, v: str) -> str:
        return (v or "").upper()

    @model_validator(mode="after")
    def validate_dim(self) -> "Settings":
        # OpenAI embedding boyutları (güncel)
        known_dims: dict[str, int] = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }
        expected = known_dims.get(self.openai_embed_model)
        if expected is not None and self.milvus_dim != expected:
            raise ValueError(
                f"MILVUS_DIM ({self.milvus_dim}) '{self.openai_embed_model}' ile uyumsuz. Beklenen: {expected}"
            )
        return self

    # --- Helpers ---
    @property
    def milvus_uri_with_port(self) -> str:
        return _ensure_port(self.milvus_uri)
    @property
    def langsmith_enabled(self) -> bool:
        return bool(self.langchain_tracing_v2 and self.langchain_api_key)

    def milvus_connect_kwargs(self) -> Dict[str, str]:
        """
        pymilvus.connections.connect(**kwargs) için argümanları üretir.
        Zilliz Serverless: {'uri': ..., 'token': ...}
        """
        return {"uri": self.milvus_uri, "token": self.milvus_token or ""}

    def milvus_index_params(self) -> Dict[str, Any]:
        m = self.milvus_metric
        t = self.milvus_index_type

        if t == "AUTOINDEX":
            return {"index_type": "AUTOINDEX", "metric_type": m, "params": {}}

        if t == "HNSW":
            return {"index_type": "HNSW", "metric_type": m, "params": {"M": 16, "efConstruction": 200}}

        if t == "IVF_FLAT":
            return {"index_type": "IVF_FLAT", "metric_type": m, "params": {"nlist": 1024}}

        if t == "IVF_SQ8":
            return {"index_type": "IVF_SQ8", "metric_type": m, "params": {"nlist": 1024}}

        if t == "IVF_PQ":
            return {"index_type": "IVF_PQ", "metric_type": m, "params": {"m": 16, "nbits": 8, "nlist": 1024}}

        # varsayılan
        return {"index_type": "AUTOINDEX", "metric_type": m, "params": {}}

    def milvus_search_params(self) -> Dict[str, Any]:
        m = self.milvus_metric
        t = self.milvus_index_type

        if t == "AUTOINDEX":
            return {"metric_type": m, "params": {}}

        if t == "HNSW":
            return {"metric_type": m, "params": {"ef": 64}}

        # IVF ailesi için tipik nprobe
        return {"metric_type": m, "params": {"nprobe": 32}}

    def openai_client_kwargs(self) -> Dict[str, str]:
        """OpenAI istemcisi için yapılandırma parametrelerini döndürür."""
        kwargs = {"api_key": self.openai_api_key}
        if self.openai_base_url:
            kwargs["base_url"] = self.openai_base_url
        return kwargs

    def safe_summary(self) -> Dict[str, str]:
        def mask(s: Optional[str]) -> str:
            if not s:
                return ""
            if len(s) <= 6:
                return "*" * len(s)
            return s[:3] + "*" * (len(s) - 5) + s[-2:]

        return {
            "OPENAI_CHAT_MODEL": self.openai_chat_model,
            "OPENAI_EMBED_MODEL": self.openai_embed_model,
            "MILVUS_URI": self.milvus_uri,
            "MILVUS_COLLECTION": self.milvus_collection,
            "MILVUS_DIM": str(self.milvus_dim),
            "MILVUS_METRIC": self.milvus_metric,
            "LANGSMITH_ENABLED": str(self.langsmith_enabled),
            "HISTORY_ENABLED": str(self.history_enabled),
            "SERVER": f"{self.server_host}:{self.server_port}",
            "CORS_ORIGINS": self.cors_origins,
            "LOG_LEVEL": self.log_level,
            # Masked secrets
            "OPENAI_API_KEY": mask(self.openai_api_key),
            "LANGCHAIN_API_KEY": mask(self.langchain_api_key),
            "MILVUS_TOKEN": mask(self.milvus_token),
        }
    

# Tekil settings nesnemiz
settings = Settings()