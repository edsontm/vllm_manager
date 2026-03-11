from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr


QueuePriorityRole = Literal["high_priority", "medium_priority", "low_priority"]


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"
    queue_priority_role: QueuePriorityRole | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None
    role: str | None = None
    queue_priority_role: QueuePriorityRole | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    queue_priority_role: QueuePriorityRole
    is_active: bool
    created_at: datetime


class UserList(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    size: int


class PasswordChange(BaseModel):
    """Used by PATCH /users/me/password — self-service, requires current password."""
    current_password: str
    new_password: str

    @property
    def min_length_ok(self) -> bool:
        return len(self.new_password) >= 8


class AdminPasswordReset(BaseModel):
    """Used by PATCH /users/{id}/password — admin resets, no current password needed."""
    new_password: str
