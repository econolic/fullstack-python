from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.schemas import UserCreate


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.scalars(select(User).where(User.id == user_id))
        return result.first()

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.session.scalars(
            select(User).where(User.username == username)
        )
        return result.first()

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.scalars(select(User).where(User.email == email))
        return result.first()

    async def create_user(self, body: UserCreate, avatar: str | None = None) -> User:
        user = User(
            username=body.username,
            email=str(body.email),
            hashed_password=body.password,
            avatar=avatar,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def confirmed_email(self, email: str) -> None:
        user = await self.get_user_by_email(email)
        if user is None:
            return
        user.confirmed = True
        await self.session.commit()

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        user = await self.get_user_by_email(email)
        if user is None:
            return None
        user.avatar = url
        await self.session.commit()
        await self.session.refresh(user)
        return user
