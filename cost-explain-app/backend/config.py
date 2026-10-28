"""Runtime settings, read once from the environment (app.yaml in Databricks Apps, shell locally)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: Literal["prod", "local"] = Field("prod", alias="APP_ENV")
    # live = query Gold on the warehouse; fixtures = bundled planted figures; auto = live, falling back to
    # fixtures only when a Gold table does not exist yet (never on permission errors).
    data_mode: Literal["live", "fixtures", "auto"] = Field("auto", alias="DATA_MODE")

    warehouse_id: str = Field("", alias="WAREHOUSE_ID")
    gold_schema: str = Field("cost_explain.gold", alias="GOLD_SCHEMA")
    # The comparison the UI opens on, sent with /api/me so the first screen loads without waiting for the list
    default_comparison: str = Field("MOM_2026-09", alias="DEFAULT_COMPARISON")

    # Lakebase (PGHOST / PGDATABASE / PGUSER / PGPORT / PGSSLMODE are injected by the postgres resource)
    lakebase_endpoint: str = Field("", alias="LAKEBASE_ENDPOINT")
    lakebase_endpoint_path: str = Field(
        "projects/cost-explain-db/branches/production/endpoints/primary", alias="LAKEBASE_ENDPOINT_PATH"
    )
    lakebase_schema: str = Field("cost_explain_app", alias="LAKEBASE_SCHEMA")

    agent_endpoint: str = Field("", alias="AGENT_ENDPOINT")
    agent_timeout_s: int = Field(180, alias="AGENT_TIMEOUT_S")  # background call: not bound by the 120 s proxy limit
    genie_space_id: str = Field("", alias="GENIE_SPACE_ID")

    analyst_group: str = Field("ce_fpa_analysts", alias="ANALYST_GROUP")
    approver_group: str = Field("ce_fpa_approvers", alias="APPROVER_GROUP")

    # Demo affordances (reset/reseed). Never enable in a real deployment.
    demo_mode: bool = Field(True, alias="APP_DEMO_MODE")

    # Local development only: identity injected by the dev middleware (ignored when APP_ENV=prod)
    local_user_email: str = Field("", alias="LOCAL_USER_EMAIL")
    local_profile: str = Field("fe-vm-zh-serverless", alias="LOCAL_DATABRICKS_PROFILE")

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
