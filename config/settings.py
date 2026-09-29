"""
Configuration Management Module.

Centralized, validated configuration using Pydantic Settings.
All secrets are loaded from environment variables — never hardcoded.

Usage:
    from config.settings import get_settings
    settings = get_settings()
    print(settings.groq_api_key)  # masked: SecretStr('**********')
"""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Groq (free tier) / GPT-OSS
    groq_api_key: SecretStr = Field(..., description="Groq API key for GPT-OSS access")
    groq_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Groq model identifier",
    )
    groq_fallback_model: str = Field(
        default="openai/gpt-oss-20b",
        description="Used when the primary model is rate-limited (empty to disable)",
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq API base URL",
    )

    # Generation parameters
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0=deterministic, 2=creative)",
    )
    llm_max_tokens: int = Field(
        default=4096,
        ge=256,
        le=32768,
        description="Maximum tokens per LLM response",
    )
    llm_timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Request timeout in seconds",
    )

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_key(cls, v: SecretStr) -> SecretStr:
        key = v.get_secret_value().strip()
        if not key:
            raise ValueError("GROQ_API_KEY must not be empty")
        if not key.startswith("gsk_"):
            raise ValueError("GROQ_API_KEY must start with 'gsk_'")
        return SecretStr(key)


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence Transformers model name",
    )
    embedding_dimension: int = Field(
        default=384,
        description="Output embedding vector dimension",
    )
    embedding_batch_size: int = Field(
        default=32,
        ge=1,
        le=512,
        description="Batch size for embedding generation",
    )
    embedding_device: Literal["cpu", "cuda", "mps"] = Field(
        default="cpu",
        description="Device for embedding inference",
    )


class VectorStoreSettings(BaseSettings):
    """ChromaDB vector store configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    chroma_persist_directory: str = Field(
        default="./data/chroma_db",
        description="Directory for ChromaDB persistence",
    )
    chroma_collection_resume: str = Field(
        default="resume_collection",
        description="ChromaDB collection name for resume chunks",
    )
    chroma_collection_jd: str = Field(
        default="jd_collection",
        description="ChromaDB collection name for JD chunks",
    )
    retrieval_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve per query",
    )
    retrieval_score_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for retrieved chunks",
    )


class ChunkingSettings(BaseSettings):
    """Document chunking configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    chunk_size: int = Field(
        default=512,
        ge=128,
        le=2048,
        description="Target chunk size in tokens",
    )
    chunk_overlap: int = Field(
        default=64,
        ge=0,
        le=512,
        description="Overlap between consecutive chunks",
    )

    @model_validator(mode="after")
    def validate_overlap_less_than_chunk(self) -> "ChunkingSettings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self


class AppSettings(BaseSettings):
    """Application-level settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field(
        default="AI Interview Preparation Assistant",
        description="Application display name",
    )
    app_version: str = Field(default="1.0.0", description="Application version")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Application log level",
    )

    # File upload limits
    max_file_size_mb: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum upload file size in MB",
    )
    allowed_resume_types: list[str] = Field(
        default=["pdf", "docx"],
        description="Allowed resume file extensions",
    )

    # Data directories
    data_directory: str = Field(
        default="./data",
        description="Root data directory",
    )
    upload_directory: str = Field(
        default="./data/uploads",
        description="Temporary file upload directory",
    )


class Settings(BaseSettings):
    """
    Master settings class — aggregates all sub-settings.

    Loads from environment variables and .env file.
    Validates all required values at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Sub-settings (composed, not inherited)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    app: AppSettings = Field(default_factory=AppSettings)

    def validate_startup(self) -> None:
        """
        Run all startup validations.

        Called once at application boot. Raises SystemExit on failure
        so the app never starts with invalid configuration.
        """
        errors: list[str] = []

        # Validate Groq key is accessible
        try:
            _ = self.llm.groq_api_key
        except Exception as e:
            errors.append(f"LLM config error: {e}")

        # Validate directories exist or can be created
        import os

        for dir_path in [
            self.app.data_directory,
            self.app.upload_directory,
            self.vector_store.chroma_persist_directory,
        ]:
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                errors.append(f"Cannot create directory '{dir_path}': {e}")

        if errors:
            print("\n[CONFIG ERROR] Application cannot start:")
            for err in errors:
                print(f"  ✗ {err}")
            print("\nCheck your .env file against .env.example\n")
            sys.exit(1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Uses lru_cache so the .env file is read only once per process.
    Call get_settings.cache_clear() in tests to reload configuration.
    """
    return Settings()
