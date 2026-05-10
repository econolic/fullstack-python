from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.schemas import (
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RequestEmail,
    Token,
    UserCreate,
    UserResponse,
)
from src.services.auth import (
    Hash,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    get_email_from_token,
    hash_token,
    utc_now,
)
from src.services.cache import invalidate_user_cache
from src.services.email import send_email, send_password_reset_email
from src.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_expired(expires_at) -> bool:
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=utc_now().tzinfo) <= utc_now()
    return expires_at <= utc_now()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user and send an email verification message."""
    user_service = UserService(db)

    if await user_service.get_user_by_email(str(user_data.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    if await user_service.get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists",
        )

    user_data.password = Hash().get_password_hash(user_data.password)
    try:
        new_user = await user_service.create_user(user_data)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists",
        )

    background_tasks.add_task(
        send_email,
        new_user.email,
        new_user.username,
        str(request.base_url),
    )
    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate a confirmed user and issue access and refresh tokens."""
    user_service = UserService(db)
    user = await user_service.get_user_by_username(form_data.username)
    if not user or not Hash().verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect login or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email address is not confirmed",
        )

    access_token = await create_access_token(data={"sub": user.username})
    refresh_token, jti, expires_at = await create_refresh_token(
        data={"sub": user.username}
    )
    await user_service.create_refresh_token(user, jti, expires_at)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token)
async def refresh_tokens(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Rotate a valid refresh token and return a new token pair."""
    payload = decode_token(body.refresh_token, "refresh")
    username: str | None = payload.get("sub")
    jti: str | None = payload.get("jti")
    if username is None or jti is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_service = UserService(db)
    refresh_token = await user_service.get_refresh_token_by_jti(jti)
    if (
        refresh_token is None
        or refresh_token.revoked_at is not None
        or _is_expired(refresh_token.expires_at)
    ):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await user_service.get_user_by_username(username)
    if user is None or not user.confirmed:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = await create_access_token(data={"sub": user.username})
    new_refresh_token, new_jti, expires_at = await create_refresh_token(
        data={"sub": user.username}
    )
    await user_service.create_refresh_token(user, new_jti, expires_at)
    await user_service.revoke_refresh_token(refresh_token, utc_now(), new_jti)
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/logout")
async def logout_user(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Revoke a refresh token."""
    payload = decode_token(body.refresh_token, "refresh")
    jti: str | None = payload.get("jti")
    if jti is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_service = UserService(db)
    refresh_token = await user_service.get_refresh_token_by_jti(jti)
    if refresh_token is not None and refresh_token.revoked_at is None:
        await user_service.revoke_refresh_token(refresh_token, utc_now())
    return {"message": "Logged out"}


@router.get("/confirmed_email/{token}")
async def confirmed_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Confirm a user email address with an email verification token."""
    email = await get_email_from_token(token)
    user_service = UserService(db)
    user = await user_service.get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification error",
        )
    if user.confirmed:
        return {"message": "Email is already confirmed"}

    await user_service.confirmed_email(email)
    await invalidate_user_cache(user.username)
    return {"message": "Email confirmed"}


@router.post("/request_email")
async def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Resend a confirmation email for an unconfirmed account."""
    user_service = UserService(db)
    user = await user_service.get_user_by_email(str(body.email))
    if user is None:
        return {"message": "Check your email for confirmation"}
    if user.confirmed:
        return {"message": "Email is already confirmed"}

    background_tasks.add_task(
        send_email,
        user.email,
        user.username,
        str(request.base_url),
    )
    return {"message": "Check your email for confirmation"}


@router.post("/password-reset/request")
async def request_password_reset(
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a one-time password reset token and send it by email."""
    user_service = UserService(db)
    user = await user_service.get_user_by_email(str(body.email))
    if user is not None:
        raw_token = create_password_reset_token()
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(
            seconds=settings.password_reset_token_expire_seconds
        )
        await user_service.create_password_reset_token(user, token_hash, expires_at)
        background_tasks.add_task(
            send_password_reset_email,
            user.email,
            user.username,
            str(request.base_url),
            raw_token,
        )
    return {"message": "If this email exists, password reset instructions were sent"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Reset a password using a valid one-time reset token."""
    user_service = UserService(db)
    reset_token = await user_service.get_password_reset_token(hash_token(body.token))
    if (
        reset_token is None
        or reset_token.used_at is not None
        or _is_expired(reset_token.expires_at)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    user = await user_service.get_user_by_id(reset_token.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    await user_service.update_password(
        user, Hash().get_password_hash(body.new_password)
    )
    await user_service.mark_password_reset_token_used(reset_token, utc_now())
    await invalidate_user_cache(user.username)
    return {"message": "Password has been reset"}
