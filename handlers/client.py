"""Клиентские сценарии: меню, запись, инфо, вопрос администратору."""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import database as db
import keyboards as kb
import scheduling
import utils
from states import Booking, Chat

logger = logging.getLogger(__name__)
router = Router(name="client")


# ─── Разбор callback_data ───
# Данные недоверенные: значение можно подделать в обход нарисованной кнопки

def _parse_date(raw: str) -> Optional[date]:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_slot(raw: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


async def _free_slots(day: date) -> list[datetime]:
    """Свободные слоты дня."""
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=config.TIMEZONE)
    taken = await db.taken_slots(day_start, day_start + timedelta(days=1))
    return [s for s in scheduling.bookable_slots(day) if s.isoformat() not in taken]


def _greeting(name: Optional[str]) -> str:
    header = (
        f"С возвращением, <b>{utils.escape(name)}</b>! 👋"
        if name
        else f"Привет! 👋\n\nЯ бот {config.BUSINESS_TITLE} "
             f"<b>{utils.escape(config.BUSINESS_NAME)}</b> в {config.BUSINESS_CITY} {config.EMOJI}"
    )
    ad = (
        f"\n\n─────────────────\n🤖 <i>Хотите такого же бота?</i>\n{config.DEV_USERNAME}"
        if config.DEV_USERNAME
        else ""
    )
    return (
        f"{header}\n\n"
        "Здесь можно записаться, узнать цены и задать вопрос 💬\n\n"
        "Выбери, что тебя интересует:\n\n"
        "<i>/menu — вернуться сюда в любой момент</i>"
        f"{ad}"
    )


# ─── Меню ───

@router.message(CommandStart())
@router.message(Command("menu"))
async def show_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    client = await db.get_client(message.from_user.id)
    name = client["name"] if client else None
    await message.answer(_greeting(name), reply_markup=kb.main_menu())


@router.callback_query(F.data == "nav:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    client = await db.get_client(callback.from_user.id)
    name = client["name"] if client else None
    await callback.message.edit_text(_greeting(name), reply_markup=kb.main_menu())
    await callback.answer()


# ─── Шаг 1: услуга ───

@router.callback_query(F.data.in_({"booking:start", "booking:restart", "nav:services"}))
async def choose_service(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.service)
    await callback.message.edit_text(
        "Выбери услугу 👇\n\n<i>Нажми, чтобы увидеть детали и цену</i>",
        reply_markup=kb.services(),
    )
    await callback.answer()


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def choose_day(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.removeprefix("svc:")
    service = config.SERVICES.get(key)
    if service is None:
        await callback.answer("Услуга недоступна, начни заново", show_alert=True)
        return

    await state.update_data(service_key=key)
    days = scheduling.available_days()
    if not days:
        await callback.answer("Свободных дней нет, напиши администратору", show_alert=True)
        return

    await callback.message.edit_text(
        f"<b>{service['name']}</b>\n\n"
        f"📝 {service['desc']}\n"
        f"⏱ {config.format_duration(service['duration_minutes'])}  ·  💰 {service['price']}\n\n"
        "Выбери удобный день:",
        reply_markup=kb.days(days),
    )
    await state.set_state(Booking.day)
    await callback.answer()


@router.callback_query(Booking.slot, F.data == "nav:days")
async def back_to_days(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.day)
    await callback.message.edit_text(
        "Выбери удобный день:", reply_markup=kb.days(scheduling.available_days())
    )
    await callback.answer()


# ─── Шаг 2: день ───

@router.callback_query(Booking.day, F.data.startswith("day:"))
async def choose_time(callback: CallbackQuery, state: FSMContext) -> None:
    day = _parse_date(callback.data.removeprefix("day:"))
    if day is None or not scheduling.is_valid_day(day):
        await callback.answer("Этот день недоступен", show_alert=True)
        return

    slots = await _free_slots(day)
    if not slots:
        await callback.answer("На этот день всё занято, выбери другой", show_alert=True)
        return

    await state.update_data(day=day.isoformat())
    await callback.message.edit_text(
        f"📅 <b>{scheduling.format_day(day)}</b> — выбери удобное время:",
        reply_markup=kb.times(slots),
    )
    await state.set_state(Booking.slot)
    await callback.answer()


# ─── Шаг 3: время ───

def _summary(name: str, phone: str, service: dict, visit_at: datetime) -> str:
    return (
        "📋 <b>Проверь данные записи:</b>\n\n"
        f"👤 Имя: {utils.escape(name)}\n"
        f"📱 Телефон: {utils.escape(phone)}\n"
        f"{config.EMOJI} Услуга: {service['name']}\n"
        f"💰 Стоимость: {service['price']}\n"
        f"⏱ Длительность: {config.format_duration(service['duration_minutes'])}\n"
        f"📅 Когда: {scheduling.format_visit(visit_at)}\n\n"
        "Всё верно?"
    )


@router.callback_query(Booking.slot, F.data.startswith("slot:"))
async def got_slot(callback: CallbackQuery, state: FSMContext) -> None:
    slot = _parse_slot(callback.data.removeprefix("slot:"))
    if slot is None or not scheduling.is_valid_slot(slot):
        await callback.answer("Это время недоступно", show_alert=True)
        return

    if slot not in await _free_slots(slot.date()):
        await callback.answer("Это время только что заняли, выбери другое", show_alert=True)
        return

    await state.update_data(slot=slot.isoformat())
    data = await state.get_data()
    service = config.SERVICES[data["service_key"]]

    client = await db.get_client(callback.from_user.id)
    if client:
        # Постоянному клиенту контакты не переспрашиваем
        await state.update_data(name=client["name"], phone=client["phone"])
        await callback.message.edit_text(
            _summary(client["name"], client["phone"], service, slot),
            reply_markup=kb.confirm(),
        )
        await state.set_state(Booking.confirm)
    else:
        await callback.message.edit_text("Отлично! Осталась пара вопросов 😊\n\nКак тебя зовут?")
        await state.set_state(Booking.name)
    await callback.answer()


# ─── Шаг 4: имя ───

@router.message(Booking.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = utils.validate_name(message.text)
    if name is None:
        await message.answer("Имя должно состоять из букв, 2–40 символов. Попробуй ещё раз:")
        return

    await state.update_data(name=name)
    await message.answer(
        f"Приятно познакомиться, {utils.escape(name)}! 😊\n\n"
        "Введи номер телефона:\n<i>Например: +996 700 123456</i>"
    )
    await state.set_state(Booking.phone)


# ─── Шаг 5: телефон ───

@router.message(Booking.phone, F.text)
async def got_phone(message: Message, state: FSMContext) -> None:
    phone = utils.validate_phone(message.text)
    if phone is None:
        await message.answer(
            "Не могу распознать номер 🤔\n\n"
            "Введи в формате +996 700 123456 или 0700123456"
        )
        return

    await state.update_data(phone=phone)
    data = await state.get_data()
    service = config.SERVICES[data["service_key"]]
    slot = datetime.fromisoformat(data["slot"])

    await message.answer(
        _summary(data["name"], phone, service, slot),
        reply_markup=kb.confirm(),
    )
    await state.set_state(Booking.confirm)


# ─── Шаг 6: подтверждение ───

@router.callback_query(Booking.confirm, F.data == "booking:confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    service = config.SERVICES[data["service_key"]]
    slot = datetime.fromisoformat(data["slot"])

    if not scheduling.is_valid_slot(slot):
        await callback.answer("Время уже прошло, выбери другое", show_alert=True)
        await choose_service(callback, state)
        return

    tg_id = callback.from_user.id
    username = f"@{callback.from_user.username}" if callback.from_user.username else "без username"
    booking_id = utils.generate_booking_id()

    try:
        await db.create_booking(
            booking_id=booking_id,
            tg_id=tg_id,
            name=data["name"],
            phone=data["phone"],
            service_key=data["service_key"],
            service_name=service["name"],
            price=service["price"],
            duration_min=service["duration_minutes"],
            visit_at=slot,
        )
    except db.SlotTakenError:
        # Гонка: слот перехватили, пока клиент заполнял форму
        await callback.answer("Это время только что заняли 😔", show_alert=True)
        await choose_service(callback, state)
        return

    await db.save_client(tg_id, username, data["name"], data["phone"])

    await callback.message.edit_text(
        "✅ <b>Заявка отправлена!</b>\n\n"
        f"Номер: <code>{booking_id}</code>\n\n"
        f"{config.EMOJI} {service['name']}\n"
        f"📅 {scheduling.format_visit(slot)}\n"
        f"📍 {utils.escape(config.BUSINESS_ADDRESS)}\n\n"
        "Администратор скоро подтвердит запись.\n\n"
        "Хочешь что-то уточнить — просто напиши сюда 💬\n"
        "/menu — главное меню"
    )

    await _notify_admin(bot, booking_id, tg_id, username, data, service, slot)

    await state.set_state(Chat.client_waiting)
    await state.update_data(tg_username=username)
    await callback.answer("Заявка отправлена!")


async def _notify_admin(
    bot: Bot,
    booking_id: str,
    tg_id: int,
    username: str,
    data: dict,
    service: dict,
    slot: datetime,
) -> None:
    await utils.safe_send(
        bot,
        config.ADMIN_ID,
        f"🔔 <b>Новая запись #{booking_id}</b>\n\n"
        f"👤 {utils.escape(data['name'])}\n"
        f"📱 {utils.escape(data['phone'])}\n"
        f"✈️ {utils.escape(username)}  |  ID: <code>{tg_id}</code>\n\n"
        f"{config.EMOJI} {service['name']}\n"
        f"💰 {service['price']}\n"
        f"⏱ {config.format_duration(service['duration_minutes'])}\n"
        f"📅 {scheduling.format_visit(slot)}",
        reply_markup=kb.admin_actions(tg_id, booking_id),
    )


# ─── Инфо-разделы ───

@router.callback_query(F.data == "info:prices")
async def show_prices(callback: CallbackQuery) -> None:
    lines = [f"{config.EMOJI} <b>Услуги и цены — {utils.escape(config.BUSINESS_NAME)}</b>\n"]
    for service in config.SERVICES.values():
        lines.append(
            f"{service['name']}\n  {service['desc']}\n"
            f"  ⏱ {config.format_duration(service['duration_minutes'])} · 💰 {service['price']}\n"
        )
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.prices_actions())
    await callback.answer()


@router.callback_query(F.data == "info:address")
async def show_address(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        f"📍 <b>Адрес:</b>\n{utils.escape(config.BUSINESS_ADDRESS)}\n\n"
        f"🕐 <b>Часы работы:</b> {config.WORK_START_HOUR:02d}:00–{config.WORK_END_HOUR:02d}:00",
        reply_markup=kb.back_to_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "info:instagram")
async def show_instagram(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        f"📸 <b>Instagram:</b>\n{utils.escape(config.BUSINESS_INSTAGRAM)}\n\n"
        "Там можно посмотреть работы перед записью 🎨",
        reply_markup=kb.back_to_menu(),
    )
    await callback.answer()


# ─── Вопрос администратору ───

@router.callback_query(F.data == "chat:ask")
async def ask_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Chat.client_waiting)
    username = (
        f"@{callback.from_user.username}" if callback.from_user.username else "без username"
    )
    await state.update_data(tg_username=username)
    await callback.message.edit_text(
        "Напиши свой вопрос — ответим в течение часа 💬\n\n"
        "<i>Сообщение будет передано администратору</i>\n"
        "/menu — главное меню",
        reply_markup=kb.back_to_menu(),
    )
    await callback.answer()


@router.message(Chat.client_waiting)
async def client_to_admin(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.text:
        await message.answer("Пока умею пересылать только текст 🙏")
        return

    data = await state.get_data()
    username = data.get("tg_username", "без username")

    delivered = await utils.safe_send(
        bot,
        config.ADMIN_ID,
        "💬 <b>Сообщение от клиента</b>\n"
        f"👤 {utils.escape(username)}  |  ID: <code>{message.from_user.id}</code>\n\n"
        f"{utils.escape(message.text)}",
        reply_markup=kb.admin_reply(message.from_user.id),
    )
    await message.answer("✓ Доставлено" if delivered else "Не удалось отправить, попробуй позже")
