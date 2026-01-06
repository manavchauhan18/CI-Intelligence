"""
Shared configuration management for all services.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Global settings for the CI Intelligence platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ci_intelligence"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Configuration
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_llm_provider: str = "openai"
    default_model: str = "gpt-4-turbo-preview"

    # Security
    hmac_secret_key: str = "change-me-in-production"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Gateway
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000

    # Orchestrator
    orchestrator_host: str = "0.0.0.0"
    orchestrator_port: int = 8001

    # Agents
    diff_agent_host: str = "0.0.0.0"
    diff_agent_port: int = 8100

    intent_agent_host: str = "0.0.0.0"
    intent_agent_port: int = 8101

    security_agent_host: str = "0.0.0.0"
    security_agent_port: int = 8102

    performance_agent_host: str = "0.0.0.0"
    performance_agent_port: int = 8103

    test_agent_host: str = "0.0.0.0"
    test_agent_port: int = 8104

    arbiter_agent_host: str = "0.0.0.0"
    arbiter_agent_port: int = 8105

    # Observability
    enable_telemetry: bool = True
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090

    # Agent Configuration
    agent_timeout_seconds: int = 300
    arbiter_wait_timeout_seconds: int = 600
    max_retries: int = 3
    retry_backoff_multiplier: int = 2


settings = Settings()
