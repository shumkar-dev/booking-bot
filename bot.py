"""Точка входа."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database as db
from handlers import admin, client
from middlewares import ThrottlingMiddleware
from reminders import reminder_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_dispatcher() -> Dispatcher:
    # MemoryStorage: состояние теряется при рестарте. При росте — RedisStorage
    dispatcher = Dispatcher(storage=MemoryStorage())

    throttling = ThrottlingMiddleware()
    dispatcher.message.middleware(throttling)
    dispatcher.callback_query.middleware(throttling)

    # Порядок важен: админский роутер первым
    dispatcher.include_router(admin.router)
    dispatcher.include_router(client.router)
    return dispatcher


async def main() -> None:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = build_dispatcher()

    await db.connect()

    # Ссылку держим: иначе задачу может собрать GC
    reminders_task = asyncio.create_task(reminder_loop(bot))

    logger.info("Бот запущен — %s %s", config.BUSINESS_TITLE, config.BUSINESS_NAME)
    try:
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types()
        )
    finally:
        reminders_task.cancel()
        try:
            await reminders_task
        except asyncio.CancelledError:
            pass
        await db.close()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
