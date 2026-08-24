"""Слой доступа к данным."""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Iterable, Optional

import aiosqlite

import config

logger = logging.getLogger(__name__)

_connection: Optional[aiosqlite.Connection] = None

# Белый список: имя колонки подставляется в SQL, параметризовать его нельзя
_REMINDER_COLUMNS = {24: "remind_24h", 2: "remind_2h"}

ACTIVE_STATUSES = ("pending", "accepted")


class SlotTakenError(Exception):
    """Слот занят другой активной записью."""


def _conn() -> aiosqlite.Connection:
    if _connection is None:
        raise RuntimeError("База не инициализирована: вызови connect() на старте")
    return _connection


async def connect() -> None:
    global _connection
    _connection = await aiosqlite.connect(config.DB_PATH)
    _connection.row_factory = aiosqlite.Row
    # WAL — меньше блокировок при параллельном чтении и записи
    await _connection.execute("PRAGMA journal_mode=WAL")
    await _connection.execute("PRAGMA foreign_keys=ON")
    await _init_schema()
    logger.info("База данных готова: %s", config.DB_PATH)


async def close() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None


async def _init_schema() -> None:
    db = _conn()
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            tg_id      INTEGER PRIMARY KEY,
            username   TEXT,
            name       TEXT NOT NULL,
            phone      TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id           TEXT PRIMARY KEY,
            tg_id        INTEGER NOT NULL,
            name         TEXT NOT NULL,
            phone        TEXT NOT NULL,
            service_key  TEXT NOT NULL,
            service_name TEXT NOT NULL,
            price        TEXT NOT NULL,
            duration_min INTEGER NOT NULL,
            visit_at     TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'pending',
            created_at   TEXT NOT NULL,
            remind_24h   INTEGER NOT NULL DEFAULT 0,
            remind_2h    INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # Защита от двойного бронирования на уровне БД
    await db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_active_slot
        ON bookings (visit_at)
        WHERE status IN ('pending', 'accepted')
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_status_visit "
        "ON bookings (status, visit_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_client ON bookings (tg_id)"
    )
    await db.commit()


# ─── Клиенты ───

async def get_client(tg_id: int) -> Optional[aiosqlite.Row]:
    async with _conn().execute(
        "SELECT * FROM clients WHERE tg_id = ?", (tg_id,)
    ) as cursor:
        return await cursor.fetchone()


async def save_client(tg_id: int, username: str, name: str, phone: str) -> None:
    await _conn().execute(
        """
        INSERT INTO clients (tg_id, username, name, phone, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(tg_id) DO UPDATE SET
            username = excluded.username,
            name     = excluded.name,
            phone    = excluded.phone
        """,
        (tg_id, username, name, phone, datetime.now(config.TIMEZONE).isoformat()),
    )
    await _conn().commit()


# ─── Записи ───

async def taken_slots(day_start: datetime, day_end: datetime) -> set[str]:
    """ISO-строки занятых слотов в интервале."""
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    query = (
        f"SELECT visit_at FROM bookings "
        f"WHERE status IN ({placeholders}) AND visit_at >= ? AND visit_at < ?"
    )
    params = (*ACTIVE_STATUSES, day_start.isoformat(), day_end.isoformat())
    async with _conn().execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return {row["visit_at"] for row in rows}


async def create_booking(
    booking_id: str,
    tg_id: int,
    name: str,
    phone: str,
    service_key: str,
    service_name: str,
    price: str,
    duration_min: int,
    visit_at: datetime,
) -> None:
    """Бросает SlotTakenError, если слот перехватили."""
    try:
        await _conn().execute(
            """
            INSERT INTO bookings (
                id, tg_id, name, phone, service_key, service_name,
                price, duration_min, visit_at, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                booking_id,
                tg_id,
                name,
                phone,
                service_key,
                service_name,
                price,
                duration_min,
                visit_at.isoformat(),
                datetime.now(config.TIMEZONE).isoformat(),
            ),
        )
        await _conn().commit()
    except sqlite3.IntegrityError as exc:
        await _conn().rollback()
        raise SlotTakenError(str(exc)) from exc


async def get_booking(booking_id: str) -> Optional[aiosqlite.Row]:
    async with _conn().execute(
        "SELECT * FROM bookings WHERE id = ?", (booking_id,)
    ) as cursor:
        return await cursor.fetchone()


async def update_booking_status(booking_id: str, status: str) -> None:
    await _conn().execute(
        "UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id)
    )
    await _conn().commit()


# ─── Напоминания ───

async def bookings_to_remind(hours: int, window_minutes: int = 20) -> Iterable[aiosqlite.Row]:
    """Записи в окне вокруг точки «визит минус hours»."""
    column = _REMINDER_COLUMNS[hours]
    moment = datetime.now(config.TIMEZONE) + timedelta(hours=hours)
    low = (moment - timedelta(minutes=window_minutes)).isoformat()
    high = (moment + timedelta(minutes=window_minutes)).isoformat()

    query = (
        f"SELECT * FROM bookings "
        f"WHERE status = 'accepted' AND {column} = 0 "
        f"AND visit_at BETWEEN ? AND ?"
    )
    async with _conn().execute(query, (low, high)) as cursor:
        return await cursor.fetchall()


async def mark_reminded(booking_id: str, hours: int) -> None:
    column = _REMINDER_COLUMNS[hours]
    await _conn().execute(
        f"UPDATE bookings SET {column} = 1 WHERE id = ?", (booking_id,)
    )
    await _conn().commit()


async def close_past_bookings() -> int:
    """Прошедшие визиты -> 'done', иначе активные копятся бесконечно."""
    cutoff = datetime.now(config.TIMEZONE).isoformat()
    cursor = await _conn().execute(
        "UPDATE bookings SET status = 'done' "
        "WHERE status IN ('pending', 'accepted') AND visit_at < ?",
        (cutoff,),
    )
    await _conn().commit()
    return cursor.rowcount
