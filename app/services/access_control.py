"""Role checks used by every privileged handler."""

from __future__ import annotations

from app.repositories.host_repository import HostRepository


class AccessControl:
    def __init__(self, *, super_admin_id: int, hosts: HostRepository) -> None:
        self._super_admin_id = super_admin_id
        self._hosts = hosts

    def is_super_admin(self, user_id: int) -> bool:
        return user_id == self._super_admin_id

    async def is_game_manager(self, user_id: int) -> bool:
        """Return current access, querying SQLite on every protected action."""
        return self.is_super_admin(user_id) or await self._hosts.is_host(user_id)
