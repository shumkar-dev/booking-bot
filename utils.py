"""Валидация ввода и безопасная отправка."""

import html
import logging
import random
import re
import string
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

logger = logging.getLogger(__name__)

NAME_PATTERN = re.compile(r"^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\s\-']{1,39}$")


def escape(text: Optional[str]) -> str:
    """Обязательно для любого пользовательского текста в HTML-сообщениях."""
    if not text:
        return ""
    return html.escape(text, quote=False)


def validate_name(raw: str) -> Optional[str]:
    name = raw.strip()
    if not NAME_PATTERN.match(name):
        return None
    return name


def validate_phone(raw: str) -> Optional[str]:
    """Нормализованный номер или None. Общее правило — последним."""
    digits = re.sub(r"[\s\-()]", "", raw.strip())

    if re.fullmatch(r"0\d{9}", digits):            # 0700123456
        return "+996" + digits[1:]
    if re.fullmatch(r"\+?996\d{9}", digits):       # +996700123456
        return "+" + digits.lstrip("+")
    if re.fullmatch(r"[78]\d{10}", digits):        # 79991234567 / 89991234567
        return "+7" + digits[1:]
    if re.fullmatch(r"\+\d{10,15}", digits):       # любой международный
        return digits
    return None


def generate_booking_id() -> str:
    """Без похожих символов: 0/O, 1/I."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(alphabet, k=6))


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    """Не бросает исключений: блокировка бота — штатная ситуация."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramForbiddenError:
        logger.info("Пользователь %s заблокировал бота", chat_id)
    except TelegramAPIError:
        logger.exception("Не удалось отправить сообщение пользователю %s", chat_id)
    return False
