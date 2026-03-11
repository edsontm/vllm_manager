from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

ResourceType = Literal["instance", "model", "token", "queue", "user"]
Action = Literal["read", "create", "update", "delete", "start", "stop", "infer"]
Effect = Literal["allow", "deny"]


class AbacPolicyCreate(BaseModel):
    subject_user_id: int | None = None
    subject_role: Literal["admin", "user"] | None = None
    resource_type: ResourceType
    resource_id: int | None = None  # None = wildcard (all resources of this type)
    action: Action
    effect: Effect = "allow"

    @model_validator(mode="after")
    def at_least_one_subject(self) -> AbacPolicyCreate:
        if self.subject_user_id is None and self.subject_role is None:
            raise ValueError("At least one of subject_user_id or subject_role must be set")
        return self


class AbacPolicyUpdate(BaseModel):
    effect: Effect | None = None
    resource_id: int | None = None


class AbacPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_user_id: int | None
    subject_role: str | None
    resource_type: str
    resource_id: int | None
    action: str
    effect: str
    created_at: datetime
    created_by_id: int | None


class AbacPolicyList(BaseModel):
    items: list[AbacPolicyRead]
    total: int
    page: int
    size: int
