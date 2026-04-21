from __future__ import annotations
from typing import Annotated
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "vllm_manager"
    debug: bool = False

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # HuggingFace
    hf_token: str = ""
    hf_cache_dir: str = "/home/vllm/.cache/huggingface"

    # vLLM container management
    vllm_base_port: int = 9000
    vllm_port_range: int = 100
    vllm_bind_host: str = "127.0.0.1"
    vllm_docker_image: str = "vllm/vllm-openai:latest"
    # Docker network that backend and vLLM containers share so the proxy can
    # reach vLLM by container name instead of host loopback.
    docker_network: str = "vllm_manager_vllm_network"

    # CORS — comma-separated string from env.
    # Canonical public host is llm.liaufms.org.
    base_url: str = "https://llm.liaufms.org"
    cors_origins: str = "https://llm.liaufms.org"

    # Queue
    queue_batch_size: int = 16
    queue_batch_timeout_ms: int = 100

    # Metrics
    metrics_poll_interval_s: int = 30

    # HuggingFace catalog worker — tuned so a full refresh stays under the
    # free-tier HF rate limit (1000 requests per 5 minutes). Increase for
    # accounts with a PRO/Enterprise plan.
    catalog_refresh_interval_s: int = 1800  # 30 minutes
    catalog_popular_limit: int = 120        # top-N by downloads + by likes
    catalog_per_task_limit: int = 40        # top-N per pipeline task (6 tasks)
    catalog_max_concurrency: int = 4        # parallel model_info fetches
    catalog_min_results_live_fallback: int = 5  # if catalog returns < N, fall back to live HF

    # Bootstrap admin account
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "16ceb20f"

    @field_validator("vllm_bind_host")
    @classmethod
    def must_be_localhost(cls, v: str) -> str:
        if v != "127.0.0.1":
            raise ValueError("vllm_bind_host MUST be 127.0.0.1 — vLLM ports must never be externally exposed")
        return v

    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or [self.base_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
