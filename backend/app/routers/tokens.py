from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_active_user, get_db
from app.schemas.token import TokenCreate, TokenCreateResponse, TokenRead, TokenUpdate
from app.services import token_service
from app.models.access_token import AccessToken

router = APIRouter(prefix="/tokens", tags=["Tokens"])


def _enrich(token: AccessToken) -> TokenRead:
    """Convert AccessToken ORM (with eagerly-loaded .user) to TokenRead, injecting owner info."""
    base = TokenRead.model_validate(token)
    if token.user is not None:
        return base.model_copy(update={
            "owner_username": token.user.username,
            "owner_queue_priority_role": token.user.queue_priority_role,
        })
    return base


@router.get("", response_model=list[TokenRead])
async def list_tokens(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List tokens. Admins see all tokens; regular users see only their own."""
    is_admin = current_user.role == "admin"
    tokens = await token_service.list_tokens(db, current_user.id, is_admin=is_admin)
    return [_enrich(t) for t in tokens]


@router.post("", response_model=TokenCreateResponse, status_code=201)
async def create_token(
    body: TokenCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API token. Admins may set `user_id` to assign it to another user."""
    # Resolve effective owner
    if body.user_id is not None and body.user_id != current_user.id:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins may create tokens for other users")
        effective_user_id = body.user_id
    else:
        effective_user_id = current_user.id

    token_orm, raw_token = await token_service.create_token(db, effective_user_id, body)

    # Re-fetch with the user eagerly loaded so _enrich can populate owner fields.
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(AccessToken).options(joinedload(AccessToken.user)).where(AccessToken.id == token_orm.id)
    )
    token_orm = result.scalar_one()

    token_data = _enrich(token_orm).model_dump()
    token_data["token"] = raw_token
    return TokenCreateResponse(**token_data)


@router.patch("/{token_id}", response_model=TokenRead)
async def update_token(
    token_id: int,
    body: TokenUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a token's name, enabled state, instance scope, or model scope.
    Only the token owner (or an admin) may call this endpoint.
    """
    token_orm = await token_service.update_token(db, token_id, body, current_user)
    return TokenRead.model_validate(token_orm)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: int,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a token. Only the owner or an admin may do this."""
    await token_service.revoke_token(db, token_id, current_user)
    return Response(status_code=204)

