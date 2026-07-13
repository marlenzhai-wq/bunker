"""Commands reserved exclusively for the single super administrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, User

from app.repositories.host_repository import HostRepository
from app.services.access_control import AccessControl


router = Router(name="administration")
audit_log = logging.getLogger("bunker.audit")


@dataclass(frozen=True, slots=True)
class HostTarget:
    user_id: int
    username: str | None
    display_name: str

    @property
    def label(self) -> str:
        return f"@{self.username}" if self.username else self.display_name


def _label(user: User) -> str:
    return user.full_name or "Ойыншы"


def _parse_target(message: Message, command: CommandObject) -> HostTarget | None:
    reply = message.reply_to_message
    if reply and reply.from_user:
        user = reply.from_user
        return HostTarget(user.id, user.username, _label(user))

    raw_id = (command.args or "").strip()
    if not raw_id:
        return None
    try:
        user_id = int(raw_id)
    except ValueError:
        return None
    if user_id <= 0:
        return None
    return HostTarget(user_id, None, f"ID: {user_id}")


async def _require_super_admin(message: Message, access: AccessControl) -> bool:
    user = message.from_user
    if user and access.is_super_admin(user.id):
        return True
    actor_id = user.id if user else None
    audit_log.warning("ADMIN_ACTION denied action=super_command actor_id=%s", actor_id)
    await message.answer("⛔ Бұл команда тек бас админге қолжетімді.")
    return False


@router.message(Command("addhost"))
async def add_host(
    message: Message,
    command: CommandObject,
    access: AccessControl,
    hosts: HostRepository,
) -> None:
    if not await _require_super_admin(message, access):
        return
    target = _parse_target(message, command)
    if target is None:
        await message.answer("Қолданылуы: /addhost <Telegram ID> немесе хабарламаға Reply жасаңыз.")
        return
    if access.is_super_admin(target.user_id):
        await message.answer("Бұл пайдаланушы — бас админ; оны жүргізуші ретінде қосудың қажеті жоқ.")
        return

    actor_id = message.from_user.id  # Checked by _require_super_admin above.
    added = await hosts.add(
        user_id=target.user_id,
        username=target.username,
        display_name=target.display_name,
        added_by=actor_id,
    )
    audit_log.info(
        "ADMIN_ACTION action=addhost actor_id=%s target_id=%s new=%s",
        actor_id,
        target.user_id,
        added,
    )
    if added:
        await message.answer(f"✅ {target.label} жүргізуші болып қосылды.")
    else:
        await message.answer(f"ℹ️ {target.label} жүргізушілер тізімінде бар еді; деректері жаңартылды.")


@router.message(Command("removehost"))
async def remove_host(
    message: Message,
    command: CommandObject,
    access: AccessControl,
    hosts: HostRepository,
) -> None:
    if not await _require_super_admin(message, access):
        return
    target = _parse_target(message, command)
    if target is None:
        await message.answer(
            "Қолданылуы: /removehost <Telegram ID> немесе хабарламаға Reply жасаңыз."
        )
        return
    if access.is_super_admin(target.user_id):
        await message.answer("Бас админді жүргізушілер тізімінен өшіру мүмкін емес.")
        return

    actor_id = message.from_user.id
    removed = await hosts.remove(target.user_id)
    audit_log.info(
        "ADMIN_ACTION action=removehost actor_id=%s target_id=%s removed=%s",
        actor_id,
        target.user_id,
        removed,
    )
    if removed:
        await message.answer(f"✅ {target.label} жүргізушілер тізімінен өшірілді.")
    else:
        await message.answer("ℹ️ Бұл пайдаланушы жүргізушілер тізімінде жоқ.")


@router.message(Command("hosts"))
async def list_hosts(
    message: Message,
    access: AccessControl,
    hosts: HostRepository,
) -> None:
    if not await _require_super_admin(message, access):
        return
    all_hosts = await hosts.list_all()
    actor_id = message.from_user.id
    audit_log.info("ADMIN_ACTION action=hosts actor_id=%s count=%s", actor_id, len(all_hosts))

    if not all_hosts:
        await message.answer("👥 Жүргізушілер\n\nТізім бос.")
        return
    lines = ["👥 Жүргізушілер", ""]
    lines.extend(f"• {host.label}" for host in all_hosts)
    await message.answer("\n".join(lines))
