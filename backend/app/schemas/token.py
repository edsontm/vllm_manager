from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenCreate(BaseModel):
    name: str
    # Admin-only: assign the token to a specific user. Non-admins are silently
    # ignored if they attempt to set this — the router enforces ownership.
    user_id: int | None = None
    scoped_instance_ids: list[int] | None = None
    scoped_model_ids: list[str] | None = None
    expires_in_days: int | None = None

    @property
    def expires_at(self) -> datetime | None:
        if self.expires_in_days:
            return datetime.now(timezone.utc) + timedelta(days=self.expires_in_days)
        return None


class TokenUpdate(BaseModel):
    """Fields the token owner is allowed to change after creation."""
    is_enabled: bool | None = None
    scoped_instance_ids: list[int] | None = None
    scoped_model_ids: list[str] | None = None
    name: str | None = None


class TokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    user_id: int
    name: str
    token: str | None = Field(default=None, validation_alias="raw_token")
    token_prefix: str
    is_enabled: bool
    scoped_instance_ids: list[int]
    scoped_model_ids: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    # Derived from the owner User — populated by the router after eager-loading.
    owner_username: str | None = None
    owner_queue_priority_role: str | None = None


class TokenCreateResponse(TokenRead):
    token: str  # raw value — shown once only
