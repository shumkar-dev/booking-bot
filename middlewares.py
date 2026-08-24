"""Антифлуд."""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import config


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = config.THROTTLE_SECONDS) -> None:
        self.rate = rate
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id == config.ADMIN_ID:
            return await handler(event, data)

        now = time.monotonic()
        previous = self._last_seen.get(user.id, 0.0)

        if now - previous < self.rate:
            if isinstance(event, CallbackQuery):
                await event.answer("Слишком быстро, подожди секунду")
            elif isinstance(event, Message):
                pass
            return None

        self._last_seen[user.id] = now
        return await handler(event, data)
