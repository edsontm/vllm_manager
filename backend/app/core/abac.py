from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError


async def authorize(
    user,
    action: str,
    resource_type: str,
    resource_id: int | None,
    db: AsyncSession,
) -> None:
    """Raise ForbiddenError if the user is not allowed to perform *action* on
    *resource_type* (optionally scoped to *resource_id*).

    Admins bypass all checks — this function returns immediately for them.
    Non-matching policy set → default deny.
    """
    if user.role == "admin":
        return

    from app.services.abac_service import evaluate  # local import – avoids circular

    result = await evaluate(user, action, resource_type, resource_id, db)
    if result == "deny":
        raise ForbiddenError("Permission denied")
