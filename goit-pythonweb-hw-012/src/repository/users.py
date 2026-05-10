from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import PasswordResetToken, RefreshToken, User, UserRole
from src.schemas import UserCreate


class UserRepository:
    """Data-access layer for user accounts, refresh tokens and password-reset tokens."""

    def __init__(self, session: AsyncSession):
        """Initialise the repository with an async database session.

        :param session: An active SQLAlchemy async session.
        :type session: AsyncSession
        """
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Look up a user by primary key.

        :param user_id: The user's database ID.
        :type user_id: int
        :returns: The matching user or ``None``.
        :rtype: User | None
        """
        result = await self.session.scalars(select(User).where(User.id == user_id))
        return result.first()

    async def get_user_by_username(self, username: str) -> User | None:
        """Look up a user by unique username.

        :param username: The username to search for.
        :type username: str
        :returns: The matching user or ``None``.
        :rtype: User | None
        """
        result = await self.session.scalars(
            select(User).where(User.username == username)
        )
        return result.first()

    async def get_user_by_email(self, email: str) -> User | None:
        """Look up a user by email address.

        :param email: The email to search for.
        :type email: str
        :returns: The matching user or ``None``.
        :rtype: User | None
        """
        result = await self.session.scalars(select(User).where(User.email == email))
        return result.first()

    async def create_user(
        self,
        body: UserCreate,
        avatar: str | None = None,
        role: str = UserRole.USER.value,
    ) -> User:
        """Create a new user row.

        The caller is expected to pass an already-hashed password inside
        ``body.password``.

        :param body: Validated registration payload (password already hashed).
        :type body: UserCreate
        :param avatar: Optional default avatar URL.
        :type avatar: str | None
        :param role: User role, defaults to ``"user"``.
        :type role: str
        :returns: The newly created user with a database-assigned ID.
        :rtype: User
        """
        user = User(
            username=body.username,
            email=str(body.email),
            hashed_password=body.password,
            avatar=avatar,
            role=role,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def confirmed_email(self, email: str) -> None:
        """Mark a user's email address as confirmed.

        Does nothing when no user with the given email exists.

        :param email: The email address to confirm.
        :type email: str
        """
        user = await self.get_user_by_email(email)
        if user is None:
            return
        user.confirmed = True
        await self.session.commit()

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        """Update a user's avatar URL.

        :param email: The user's email address.
        :type email: str
        :param url: The new avatar URL (typically a Cloudinary link).
        :type url: str
        :returns: The updated user or ``None`` if not found.
        :rtype: User | None
        """
        user = await self.get_user_by_email(email)
        if user is None:
            return None
        user.avatar = url
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_password(self, user: User, hashed_password: str) -> User:
        """Replace a user's password hash.

        :param user: The user whose password is being changed.
        :type user: User
        :param hashed_password: The new bcrypt hash.
        :type hashed_password: str
        :returns: The updated user instance.
        :rtype: User
        """
        user.hashed_password = hashed_password
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def create_refresh_token(
        self, user: User, jti: str, expires_at: datetime
    ) -> RefreshToken:
        """Persist a refresh-token record for later validation.

        :param user: The token owner.
        :type user: User
        :param jti: JWT ID (unique identifier embedded in the JWT).
        :type jti: str
        :param expires_at: Absolute expiry timestamp.
        :type expires_at: datetime
        :returns: The persisted refresh-token row.
        :rtype: RefreshToken
        """
        refresh_token = RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at)
        self.session.add(refresh_token)
        await self.session.commit()
        await self.session.refresh(refresh_token)
        return refresh_token

    async def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        """Find a refresh-token record by its JWT ID.

        :param jti: The JWT ID to look up.
        :type jti: str
        :returns: The matching record or ``None``.
        :rtype: RefreshToken | None
        """
        result = await self.session.scalars(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.first()

    async def revoke_refresh_token(
        self,
        refresh_token: RefreshToken,
        revoked_at: datetime,
        replaced_by_jti: str | None = None,
    ) -> RefreshToken:
        """Mark a refresh token as revoked.

        During token rotation the ``replaced_by_jti`` field records which
        new token superseded this one, enabling revocation-chain auditing.

        :param refresh_token: The token record to revoke.
        :type refresh_token: RefreshToken
        :param revoked_at: The revocation timestamp.
        :type revoked_at: datetime
        :param replaced_by_jti: JTI of the successor token, if any.
        :type replaced_by_jti: str | None
        :returns: The updated token record.
        :rtype: RefreshToken
        """
        refresh_token.revoked_at = revoked_at
        refresh_token.replaced_by_jti = replaced_by_jti
        await self.session.commit()
        await self.session.refresh(refresh_token)
        return refresh_token

    async def create_password_reset_token(
        self,
        user: User,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Persist a hashed one-time password-reset token.

        Only the SHA-256 hash of the raw token is stored; the plaintext
        is sent to the user via email and never persisted.

        :param user: The user requesting the reset.
        :type user: User
        :param token_hash: SHA-256 hex digest of the raw token.
        :type token_hash: str
        :param expires_at: Absolute expiry timestamp.
        :type expires_at: datetime
        :returns: The persisted reset-token row.
        :rtype: PasswordResetToken
        """
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(reset_token)
        await self.session.commit()
        await self.session.refresh(reset_token)
        return reset_token

    async def get_password_reset_token(
        self, token_hash: str
    ) -> PasswordResetToken | None:
        """Find a password-reset token record by its SHA-256 hash.

        :param token_hash: The SHA-256 hex digest to look up.
        :type token_hash: str
        :returns: The matching record or ``None``.
        :rtype: PasswordResetToken | None
        """
        result = await self.session.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
        return result.first()

    async def mark_password_reset_token_used(
        self, reset_token: PasswordResetToken, used_at: datetime
    ) -> PasswordResetToken:
        """Mark a password-reset token as consumed.

        Once ``used_at`` is set the token cannot be reused.

        :param reset_token: The token record to mark.
        :type reset_token: PasswordResetToken
        :param used_at: The consumption timestamp.
        :type used_at: datetime
        :returns: The updated token record.
        :rtype: PasswordResetToken
        """
        reset_token.used_at = used_at
        await self.session.commit()
        await self.session.refresh(reset_token)
        return reset_token
