"""
Модуль Clone — копирование профиля указанного пользователя (имя, фамилия,
описание, аватар) с возможностью отката. Не требует прав в чате, так как
меняет только профиль самого аккаунта.
"""
from __future__ import annotations

import datetime as dt
import io

from sqlalchemy import select
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import DeletePhotosRequest, UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest

from app.db import ProfileBackup, async_session_factory
from app.modules.base import CommandContext, command


@command("clone", module="clone", description="Скопировать профиль пользователя")
async def cmd_clone(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(ProfileBackup).where(
                ProfileBackup.account_id == ctx.account_id, ProfileBackup.restored_at.is_(None)
            )
        )
        if result.scalar_one_or_none():
            await ctx.event.reply("❌ У вас уже есть активный клон. Сначала выполните .unclone.")
            return

    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}clone <кто>")
        return

    target = await ctx.client.get_entity(ctx.args[0])
    full = await ctx.client(GetFullUserRequest(target))

    me = await ctx.client.get_me()

    # Сохраняем текущий (оригинальный) профиль.
    async with async_session_factory() as session:
        backup = ProfileBackup(
            account_id=ctx.account_id,
            original_first_name=me.first_name,
            original_last_name=me.last_name,
            original_about="",
        )
        session.add(backup)
        await session.commit()

    await ctx.client(
        UpdateProfileRequest(
            first_name=target.first_name or "",
            last_name=target.last_name or "",
            about=full.full_user.about or "",
        )
    )

    photos = await ctx.client.get_profile_photos(target, limit=1)
    if photos:
        photo_bytes = await ctx.client.download_media(photos[0], file=bytes)
        file = await ctx.client.upload_file(io.BytesIO(photo_bytes), file_name="avatar.jpg")
        await ctx.client(UploadProfilePhotoRequest(file=file))

    await ctx.event.reply(f"✅ Профиль скопирован с {target.first_name}. Откат: .unclone")


@command("unclone", module="clone", description="Восстановить оригинальный профиль")
async def cmd_unclone(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(ProfileBackup)
            .where(ProfileBackup.account_id == ctx.account_id, ProfileBackup.restored_at.is_(None))
            .order_by(ProfileBackup.cloned_at.desc())
        )
        backup = result.scalar_one_or_none()
        if not backup:
            await ctx.event.reply("❌ Активного клона не найдено.")
            return

        await ctx.client(
            UpdateProfileRequest(
                first_name=backup.original_first_name or "",
                last_name=backup.original_last_name or "",
                about=backup.original_about or "",
            )
        )

        photos = await ctx.client.get_profile_photos("me")
        if photos:
            await ctx.client(DeletePhotosRequest(id=[p.to_input_photo() for p in photos]))

        backup.restored_at = dt.datetime.now(dt.timezone.utc)
        await session.commit()

    await ctx.event.reply("✅ Оригинальный профиль восстановлен.")
