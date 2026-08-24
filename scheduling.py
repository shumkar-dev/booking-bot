"""Расписание: слоты вычисляются из графика работы, а не задаются константами."""

from datetime import date, datetime, timedelta

import config


def now() -> datetime:
    """Время в часовом поясе бизнеса, не в системном."""
    return datetime.now(config.TIMEZONE)


def available_days() -> list[date]:
    """Ближайшие рабочие дни, начиная с сегодняшнего."""
    days: list[date] = []
    cursor = now().date()
    # Верхняя граница перебора — на случай пустого WORKDAYS
    for _ in range(config.DAYS_AHEAD * 4):
        if len(days) >= config.DAYS_AHEAD:
            break
        if cursor.weekday() in config.WORKDAYS:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def day_slots(day: date) -> list[datetime]:
    """Все слоты рабочего дня без учёта занятости."""
    if day.weekday() not in config.WORKDAYS:
        return []

    slots: list[datetime] = []
    cursor = datetime.combine(day, datetime.min.time(), tzinfo=config.TIMEZONE)
    cursor = cursor.replace(hour=config.WORK_START_HOUR)
    end = cursor.replace(hour=config.WORK_END_HOUR)

    while cursor < end:
        slots.append(cursor)
        cursor += timedelta(minutes=config.SLOT_STEP_MINUTES)
    return slots


def bookable_slots(day: date) -> list[datetime]:
    """Слоты без прошедшего времени и ближайшего MIN_LEAD_MINUTES."""
    threshold = now() + timedelta(minutes=config.MIN_LEAD_MINUTES)
    return [slot for slot in day_slots(day) if slot >= threshold]


def is_valid_day(day: date) -> bool:
    return day in available_days()


def is_valid_slot(slot: datetime) -> bool:
    """Валидация слота из callback_data — данные недоверенные."""
    return slot in bookable_slots(slot.date())


def format_day(day: date) -> str:
    """Метка дня для кнопок."""
    today = now().date()
    delta = (day - today).days
    if delta == 0:
        return "Сегодня"
    if delta == 1:
        return "Завтра"
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return f"{day.day:02d}.{day.month:02d} ({weekdays[day.weekday()]})"


def format_visit(visit_at: datetime) -> str:
    """Например: «Завтра в 14:00»."""
    return f"{format_day(visit_at.date())} в {visit_at:%H:%M}"
