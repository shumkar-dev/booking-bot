"""Администраторские сценарии. Права проверяются фильтром роутера."""

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import database as db
import keyboards as kb
import scheduling
import utils
from states import Chat

logger = logging.getLogger(__name__)

router = Router(name="admin")
# Фильтр на роутере, а не в теле хендлеров — забыть в новом невозможно
router.message.filter(F.from_user.id == config.ADMIN_ID)
router.callback_query.filter(F.from_user.id == config.ADMIN_ID)


async def _append_status(callback: CallbackQuery, status: str) -> None:
    """Дописывает статус к карточке. html_text, не text — иначе слетит разметка."""
    try:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{status}", reply_markup=None
        )
    except TelegramBadRequest:
        logger.warning("Не удалось отредактировать карточку заявки")


@router.callback_query(F.data.startswith("adm:accept:"))
async def accept_booking(callback: CallbackQuery, bot: Bot) -> None:
    booking_id = callback.data.removeprefix("adm:accept:")
    booking = await db.get_booking(booking_id)
    if booking is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    await db.update_booking_status(booking_id, "accepted")
    visit_at = datetime.fromisoformat(booking["visit_at"])

    await utils.safe_send(
        bot,
        booking["tg_id"],
        "✅ <b>Запись подтверждена!</b>\n\n"
        f"{utils.escape(config.BUSINESS_NAME)} ждёт тебя {config.EMOJI}\n"
        f"📅 {scheduling.format_visit(visit_at)}\n"
        f"📍 {utils.escape(config.BUSINESS_ADDRESS)}\n\n"
        "Напомню за 24 часа и за 2 часа до визита 🔔\n\n"
        "/menu — главное меню",
        reply_markup=kb.dev_ad(),
    )
    await _append_status(callback, "✅ <b>Принято</b>")
    await callback.answer("Клиент уведомлён")


@router.callback_query(F.data.startswith("adm:reject:"))
async def reject_booking(callback: CallbackQuery, bot: Bot) -> None:
    booking_id = callback.data.removeprefix("adm:reject:")
    booking = await db.get_booking(booking_id)
    if booking is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    # 'rejected' выводит запись из активных — слот освобождается
    await db.update_booking_status(booking_id, "rejected")

    await utils.safe_send(
        bot,
        booking["tg_id"],
        "😔 К сожалению, это время уже занято.\n\n"
        "Нажми /menu, чтобы выбрать другое.",
    )
    await _append_status(callback, "❌ <b>Отклонено</b>")
    await callback.answer("Клиент уведомлён")


@router.callback_query(F.data.startswith("adm:call:"))
async def call_client(callback: CallbackQuery, bot: Bot) -> None:
    booking_id = callback.data.removeprefix("adm:call:")
    booking = await db.get_booking(booking_id)
    if booking is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    await utils.safe_send(
        bot,
        booking["tg_id"],
        f"📞 Администратор {utils.escape(config.BUSINESS_NAME)} "
        "скоро позвонит для уточнения деталей.",
    )
    await _append_status(callback, "📞 <b>Перезвонит администратор</b>")
    await callback.answer("Клиент уведомлён")


# ─── Переписка с клиентом ───

@router.callback_query(F.data.startswith("adm:write:"))
async def start_writing(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.removeprefix("adm:write:")
    try:
        client_id = int(raw)
    except ValueError:
        await callback.answer("Некорректный ID клиента", show_alert=True)
        return

    await state.set_state(Chat.admin_writing)
    await state.update_data(target_client_id=client_id)
    await callback.message.answer(
        f"Пишешь клиенту <code>{client_id}</code>.\n"
        "Каждое следующее сообщение уйдёт ему.",
        reply_markup=kb.stop_chat(),
    )
    await callback.answer()


@router.message(Chat.admin_writing, F.text)
async def admin_to_client(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    client_id = data.get("target_client_id")
    if client_id is None:
        await message.answer("Не выбран клиент. Нажми «Ответить» под заявкой.")
        return

    delivered = await utils.safe_send(
        bot,
        client_id,
        f"💬 <b>{utils.escape(config.BUSINESS_NAME)}:</b>\n\n{utils.escape(message.text)}",
    )
    await message.answer("✓ Доставлено" if delivered else "Клиент недоступен")


@router.callback_query(F.data == "adm:stopchat")
async def stop_chat(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Диалог завершён.", reply_markup=None)
    await callback.answer()
