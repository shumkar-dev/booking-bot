"""Фоновый цикл напоминаний."""

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

import config
import database as db
import scheduling
import utils

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 300


async def _send_reminder(bot: Bot, booking, hours: int) -> None:
    visit_at = datetime.fromisoformat(booking["visit_at"])

    if hours == 24:
        text = (
            "🔔 <b>Напоминание</b>\n\n"
            f"Завтра у тебя запись в {utils.escape(config.BUSINESS_NAME)} {config.EMOJI}\n"
            f"🕐 {visit_at:%H:%M}\n"
            f"{config.EMOJI} {booking['service_name']}\n"
            f"📍 {utils.escape(config.BUSINESS_ADDRESS)}\n\n"
            "Ждём тебя!"
        )
    else:
        text = (
            "⏰ <b>Через 2 часа!</b>\n\n"
            f"Скоро твоя запись в {utils.escape(config.BUSINESS_NAME)} {config.EMOJI}\n"
            f"🕐 {visit_at:%H:%M}\n"
            f"📍 {utils.escape(config.BUSINESS_ADDRESS)}\n\n"
            "Не опаздывай 😊"
        )

    await utils.safe_send(bot, booking["tg_id"], text)
    # Помечаем независимо от результата: ретраить заблокировавшего смысла нет
    await db.mark_reminded(booking["id"], hours)


async def reminder_loop(bot: Bot) -> None:
    await asyncio.sleep(5)
    while True:
        try:
            closed = await db.close_past_bookings()
            if closed:
                logger.info("Закрыто прошедших записей: %s", closed)

            for hours in (24, 2):
                for booking in await db.bookings_to_remind(hours):
                    await _send_reminder(bot, booking, hours)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка в цикле напоминаний")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
