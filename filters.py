"""Рұқсаттарды тексеруге арналған фильтрлер."""
from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import SUPER_ADMIN_ID
from database.host_repository import host_repository


class IsSuperAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == SUPER_ADMIN_ID


class IsHost(BaseFilter):
    """Бас админ де жүргізуші құқығына автоматты түрде ие болады."""

    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        user_id = message.from_user.id
        if user_id == SUPER_ADMIN_ID:
            return True
        return await host_repository.is_host(user_id)
