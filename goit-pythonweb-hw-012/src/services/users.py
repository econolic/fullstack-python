from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import PasswordResetToken, RefreshToken, User, UserRole
from src.repository.users import UserRepository
from src.schemas import UserCreate
from src.services.avatar import AvatarService


class UserService:
    """Application-level service for user-related workflows.

    Orchestrates :class:`~src.repository.users.UserRepository` and
    :class:`~src.services.avatar.AvatarService` to keep the API layer
    thin.
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        repository: UserRepository | None = None,
        avatar_service: AvatarService | None = None,
    ):
        """Create a service instance.

        Either *session* or *repository* must be supplied.  When only
        *session* is given a default :class:`UserRepository` is created
        automatically.

        :param session: An async database session (used when *repository* is ``None``).
        :type session: AsyncSession | None
        :param repository: A pre-built repository (useful for testing).
        :type repository: UserRepository | None
        :param avatar_service: Avatar resolver; defaults to :class:`AvatarService`.
        :type avatar_service: AvatarService | None
        :raises ValueError: If neither *session* nor *repository* is provided.
        """
        if repository is None:
            if session is None:
                raise ValueError("Either session or repository must be provided")
            repository = UserRepository(session)
        self.repository = repository
        self.avatar_service = avatar_service or AvatarService()

    async def create_user(
        self, body: UserCreate, role: str = UserRole.USER.value
    ) -> User:
        """Register a new user with a Gravatar default avatar.

        :param body: Validated registration payload.
        :type body: UserCreate
        :param role: Initial role, defaults to ``"user"``.
        :type role: str
        :returns: The persisted user.
        :rtype: User
        """
        avatar = self.avatar_service.get_default_avatar(str(body.email))
        return await self.repository.create_user(body, avatar, role)

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Look up a user by primary key.

        :param user_id: The user's database ID.
        :type user_id: int
        :returns: The user or ``None``.
        :rtype: User | None
        """
        return await self.repository.get_user_by_id(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Look up a user by unique username.

        :param username: The username to search for.
        :type username: str
        :returns: The user or ``None``.
        :rtype: User | None
        """
        return await self.repository.get_user_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """Look up a user by email address.

        :param email: The email to search for.
        :type email: str
        :returns: The user or ``None``.
        :rtype: User | None
        """
        return await self.repository.get_user_by_email(email)

    async def confirmed_email(self, email: str) -> None:
        """Mark a user's email address as confirmed.

        :param email: The email to confirm.
        :type email: str
        """
        await self.repository.confirmed_email(email)

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        """Update a user's avatar URL.

        :param email: The user's email.
        :type email: str
        :param url: New avatar URL.
        :type url: str
        :returns: The updated user or ``None``.
        :rtype: User | None
        """
        return await self.repository.update_avatar_url(email, url)

    async def update_password(self, user: User, hashed_password: str) -> User:
        """Replace a user's password hash.

        :param user: The user to update.
        :type user: User
        :param hashed_password: The new bcrypt hash.
        :type hashed_password: str
        :returns: The updated user.
        :rtype: User
        """
        return await self.repository.update_password(user, hashed_password)

    async def create_refresh_token(
        self, user: User, jti: str, expires_at
    ) -> RefreshToken:
        """Persist a refresh-token record.

        :param user: The token owner.
        :type user: User
        :param jti: JWT ID embedded in the token.
        :type jti: str
        :param expires_at: Absolute expiry timestamp.
        :returns: The persisted record.
        :rtype: RefreshToken
        """
        return await self.repository.create_refresh_token(user, jti, expires_at)

    async def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        """Find a refresh-token record by its JWT ID.

        :param jti: The JWT ID to look up.
        :type jti: str
        :returns: The matching record or ``None``.
        :rtype: RefreshToken | None
        """
        return await self.repository.get_refresh_token_by_jti(jti)

    async def revoke_refresh_token(
        self,
        refresh_token: RefreshToken,
        revoked_at,
        replaced_by_jti: str | None = None,
    ) -> RefreshToken:
        """Revoke a refresh token, optionally recording its successor.

        :param refresh_token: The token record to revoke.
        :type refresh_token: RefreshToken
        :param revoked_at: Revocation timestamp.
        :param replaced_by_jti: JTI of the successor token, if any.
        :type replaced_by_jti: str | None
        :returns: The updated record.
        :rtype: RefreshToken
        """
        return await self.repository.revoke_refresh_token(
            refresh_token, revoked_at, replaced_by_jti
        )

    async def create_password_reset_token(
        self, user: User, token_hash: str, expires_at
    ) -> PasswordResetToken:
        """Persist a hashed one-time password-reset token.

        :param user: The user requesting the reset.
        :type user: User
        :param token_hash: SHA-256 hex digest of the raw token.
        :type token_hash: str
        :param expires_at: Absolute expiry timestamp.
        :returns: The persisted record.
        :rtype: PasswordResetToken
        """
        return await self.repository.create_password_reset_token(
            user, token_hash, expires_at
        )

    async def get_password_reset_token(
        self, token_hash: str
    ) -> PasswordResetToken | None:
        """Find a password-reset token by its SHA-256 hash.

        :param token_hash: The hash to look up.
        :type token_hash: str
        :returns: The matching record or ``None``.
        :rtype: PasswordResetToken | None
        """
        return await self.repository.get_password_reset_token(token_hash)

    async def mark_password_reset_token_used(
        self, reset_token: PasswordResetToken, used_at
    ) -> PasswordResetToken:
        """Mark a password-reset token as consumed so it cannot be reused.

        :param reset_token: The token record to mark.
        :type reset_token: PasswordResetToken
        :param used_at: Consumption timestamp.
        :returns: The updated record.
        :rtype: PasswordResetToken
        """
        return await self.repository.mark_password_reset_token_used(
            reset_token, used_at
        )
