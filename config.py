"""Конфигурация. Секреты — только из окружения, без дефолтов."""

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Не задана обязательная переменная окружения {name}. "
            f"Скопируй .env.example в .env и заполни его."
        )
    return value


def _required_int(name: str) -> int:
    raw = _required(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} должна быть числом, получено: {raw!r}") from exc


# ─── Секреты ───
BOT_TOKEN: str = _required("BOT_TOKEN")
ADMIN_ID: int = _required_int("ADMIN_ID")

# ─── Данные бизнеса ───
BUSINESS_TYPE = os.getenv("BUSINESS_TYPE", "salon")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Beauty Studio")
BUSINESS_CITY = os.getenv("BUSINESS_CITY", "Бишкек")
BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "ул. Чуй 150, каб. 12")
BUSINESS_INSTAGRAM = os.getenv("BUSINESS_INSTAGRAM", "@beauty_studio")
DEV_USERNAME = os.getenv("DEV_USERNAME", "")

DB_PATH = os.getenv("DB_PATH", "bot.db")

# ─── Часовой пояс ───
# На VPS системное время обычно UTC — задаём явно, иначе поедут напоминания
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Bishkek"))

# ─── График работы ───
WORK_START_HOUR = int(os.getenv("WORK_START_HOUR", "9"))
WORK_END_HOUR = int(os.getenv("WORK_END_HOUR", "20"))
SLOT_STEP_MINUTES = int(os.getenv("SLOT_STEP_MINUTES", "60"))
DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", "3"))
# 0 = понедельник ... 6 = воскресенье
WORKDAYS = {0, 1, 2, 3, 4, 5}
# Запас до визита, ближе которого слот не показываем
MIN_LEAD_MINUTES = int(os.getenv("MIN_LEAD_MINUTES", "60"))

# ─── Антифлуд ───
THROTTLE_SECONDS = float(os.getenv("THROTTLE_SECONDS", "0.7"))

# ─── Оформление ───
_EMOJI_BY_TYPE = {
    "salon": "💅",
    "barbershop": "✂️",
    "spa": "🧖",
    "clinic": "🏥",
    "flowers": "💐",
}
_TITLE_BY_TYPE = {
    "salon": "Салон красоты",
    "barbershop": "Барбершоп",
    "spa": "СПА-студия",
    "clinic": "Клиника",
    "flowers": "Цветочный салон",
}

EMOJI = _EMOJI_BY_TYPE.get(BUSINESS_TYPE, "⭐")
BUSINESS_TITLE = _TITLE_BY_TYPE.get(BUSINESS_TYPE, "Студия")

# ─── Услуги ───
# duration_minutes — числом, не строкой: участвует в расчётах
SERVICES: dict[str, dict] = {
    "manicure": {
        "name": f"{EMOJI} Маникюр",
        "price": "1 200 сом",
        "duration_minutes": 60,
        "desc": "Гель-лак, форма, обработка кутикулы",
    },
    "pedicure": {
        "name": f"{EMOJI} Педикюр",
        "price": "1 600 сом",
        "duration_minutes": 90,
        "desc": "Обработка стоп, покрытие",
    },
    "combo": {
        "name": f"{EMOJI} Маникюр + педикюр",
        "price": "2 500 сом",
        "duration_minutes": 150,
        "desc": "Комплекс, выгода 300 сом",
    },
    "extension": {
        "name": f"{EMOJI} Наращивание",
        "price": "2 800 сом",
        "duration_minutes": 180,
        "desc": "Акрил или гель",
    },
    "correction": {
        "name": f"{EMOJI} Коррекция",
        "price": "800 сом",
        "duration_minutes": 30,
        "desc": "Правка формы и покрытия",
    },
}


def format_duration(minutes: int) -> str:
    """90 -> '1 ч 30 мин', 60 -> '1 ч', 30 -> '30 мин'."""
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"
