"""Клавиатуры. callback_data: префикс + ISO-дата, разбирается однозначно."""

from datetime import date, datetime

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import scheduling


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Записаться", callback_data="booking:start")
    builder.button(text="💰 Услуги и цены", callback_data="info:prices")
    builder.button(text="📍 Как добраться", callback_data="info:address")
    if config.BUSINESS_INSTAGRAM:
        builder.button(text="📸 Instagram", callback_data="info:instagram")
    builder.button(text="❓ Задать вопрос", callback_data="chat:ask")
    builder.adjust(1)
    return builder.as_markup()


def services() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, service in config.SERVICES.items():
        builder.button(
            text=f"{service['name']} — {service['price']}",
            callback_data=f"svc:{key}",
        )
    builder.button(text="◀️ Назад", callback_data="nav:menu")
    builder.adjust(1)
    return builder.as_markup()


def days(available: list[date]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for day in available:
        builder.button(
            text=scheduling.format_day(day),
            callback_data=f"day:{day.isoformat()}",
        )
    builder.button(text="◀️ Назад", callback_data="nav:services")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def times(slots: list[datetime]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=f"{slot:%H:%M}", callback_data=f"slot:{slot.isoformat()}")
    builder.button(text="◀️ Назад", callback_data="nav:days")
    builder.adjust(3)
    return builder.as_markup()


def confirm() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="booking:confirm")
    builder.button(text="✏️ Изменить", callback_data="booking:restart")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="nav:menu")
    return builder.as_markup()


def prices_actions() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Записаться", callback_data="booking:start")
    builder.button(text="◀️ Назад", callback_data="nav:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_actions(client_id: int, booking_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data=f"adm:accept:{booking_id}")
    builder.button(text="❌ Отклонить", callback_data=f"adm:reject:{booking_id}")
    builder.button(text="✏️ Написать клиенту", callback_data=f"adm:write:{client_id}")
    builder.button(text="📞 Перезвонить", callback_data=f"adm:call:{booking_id}")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def admin_reply(client_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Ответить", callback_data=f"adm:write:{client_id}")
    return builder.as_markup()


def stop_chat() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔚 Завершить диалог", callback_data="adm:stopchat")
    return builder.as_markup()


def dev_ad() -> InlineKeyboardMarkup | None:
    if not config.DEV_USERNAME:
        return None
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🤖 Хочу такого же бота",
        url=f"https://t.me/{config.DEV_USERNAME.lstrip('@')}",
    )
    return builder.as_markup()
