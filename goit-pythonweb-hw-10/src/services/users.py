from libgravatar import Gravatar
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.repository.users import UserRepository
from src.schemas import UserCreate


class UserService:
    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)

    async def create_user(self, body: UserCreate) -> User:
        avatar = None
        try:
            avatar = Gravatar(str(body.email)).get_image()
        except Exception:
            avatar = None
        return await self.repository.create_user(body, avatar)

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self.repository.get_user_by_id(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        return await self.repository.get_user_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.repository.get_user_by_email(email)

    async def confirmed_email(self, email: str) -> None:
        await self.repository.confirmed_email(email)

    async def update_avatar_url(self, email: str, url: str) -> User | None:
        return await self.repository.update_avatar_url(email, url)
