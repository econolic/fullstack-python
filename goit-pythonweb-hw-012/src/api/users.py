from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.schemas import UserResponse
from src.services.auth import get_current_admin_user, get_current_user
from src.services.cache import invalidate_user_cache
from src.services.upload_file import UploadFileError, UploadFileService
from src.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/me",
    response_model=UserResponse,
    description="No more than 10 requests per minute",
)
@limiter.limit("10/minute")
async def me(
    request: Request,
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(user)


@router.patch("/avatar", response_model=UserResponse)
async def update_avatar_user(
    file: UploadFile = File(...),
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the current admin user's avatar through Cloudinary."""
    try:
        avatar_url = UploadFileService(
            settings.cld_name,
            settings.cld_api_key,
            settings.cld_api_secret,
        ).upload_file(file, user.username)
    except UploadFileError:
        raise HTTPException(
            status_code=503,
            detail="Avatar upload service is unavailable",
        )

    updated_user = await UserService(db).update_avatar_url(user.email, avatar_url)
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await invalidate_user_cache(updated_user.username)
    return UserResponse.model_validate(updated_user)
