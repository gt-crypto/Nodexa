"""Centralized Configuration and Startup Validation for Nodal Sentinel.

Provides type-safe, Pydantic-based configuration management with strict
startup validation, secret masking, and environment safety guards.
"""
import os
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """System-wide configuration settings with validation."""

    # Environment & Network
    environment: str = Field(default="development", description="Runtime environment (development, staging, production, test)")
    host: str = Field(default="127.0.0.1", description="API server bind host")
    port: int = Field(default=8000, description="API server port")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./nodal_sentinel.db",
        description="SQLAlchemy Database URL",
    )

    # LLM Provider Configuration
    llm_provider: str = Field(default="mock", description="LLM provider: mock, openai, gemini, anthropic")
    llm_model: str = Field(default="gpt-4o-mini", description="Model name")
    llm_api_key: Optional[str] = Field(default=None, description="LLM API key (masked in logs)")
    llm_temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Sampling temperature")
    llm_max_tokens: int = Field(default=2048, ge=256, le=8192, description="Max response tokens")

    # Timeouts & Limits
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Default API timeout in seconds")
    approval_expiry_hours: int = Field(default=24, ge=1, le=168, description="Remediation approval validity window")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts for idempotent operations")

    # Financial & Risk Thresholds (Paise minor units)
    max_automated_remediation_paise: int = Field(
        default=5000000,  # ₹50,000.00
        ge=0,
        description="Maximum minor unit threshold for single-operator automated remediation without dual-approval",
    )
    critical_exposure_threshold_paise: int = Field(
        default=10000000,  # ₹1,00,000.00
        ge=0,
        description="Exposure threshold classifying an exception as CRITICAL materiality",
    )
    pattern_miner_min_cluster_size: int = Field(
        default=2,
        ge=2,
        description="Minimum exception count required to form a recurring pattern cluster",
    )


    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = {"development", "staging", "production", "test"}
        v_clean = v.strip().lower()
        if v_clean not in valid_envs:
            raise ValueError(f"Invalid environment '{v}'. Must be one of: {', '.join(valid_envs)}")
        return v_clean

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        valid_providers = {"mock", "openai", "gemini", "anthropic"}
        v_clean = v.strip().lower()
        if v_clean not in valid_providers:
            raise ValueError(f"Invalid LLM provider '{v}'. Must be one of: {', '.join(valid_providers)}")
        return v_clean

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not (v.startswith("sqlite") or v.startswith("postgresql") or v.startswith("postgres")):
            raise ValueError(f"Unsupported database URL scheme in '{v}'. Must start with sqlite or postgresql.")
        return v

    def validate_startup(self) -> None:
        """Enforces mandatory production-readiness checks at startup.
        
        Raises:
            ValueError: If critical configuration requirements are unmet.
        """
        if self.environment == "production":
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is prohibited in production environment. Configure PostgreSQL.")
            if self.llm_provider != "mock" and not self.llm_api_key:
                raise ValueError(f"LLM_API_KEY is required for provider '{self.llm_provider}' in production.")
            if "http://localhost:3000" in self.allowed_origins:
                raise ValueError("Localhost origins are prohibited in production CORS settings.")

    def masked_dict(self) -> dict:
        """Returns configuration dictionary with secrets safely masked."""
        data = self.model_dump()
        if data.get("llm_api_key"):
            key = data["llm_api_key"]
            data["llm_api_key"] = f"***{key[-4:]}" if len(key) >= 8 else "***"
        return data


def load_settings() -> Settings:
    """Loads settings from environment variables with safe defaults."""
    raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        allowed_origins=origins,
        database_url=os.getenv("DATABASE_URL", "sqlite:///./nodal_sentinel.db"),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
        approval_expiry_hours=int(os.getenv("APPROVAL_EXPIRY_HOURS", "24")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        max_automated_remediation_paise=int(os.getenv("MAX_AUTOMATED_REMEDIATION_PAISE", "5000000")),
        critical_exposure_threshold_paise=int(os.getenv("CRITICAL_EXPOSURE_THRESHOLD_PAISE", "10000000")),
        pattern_miner_min_cluster_size=int(os.getenv("PATTERN_MINER_MIN_CLUSTER_SIZE", "2")),
    )



# Singleton instance
settings = load_settings()
