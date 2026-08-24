"""Тесты валидации и расписания. Запуск: BOT_TOKEN=x ADMIN_ID=1 pytest"""

import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_ID", "1")

import config  # noqa: E402
import scheduling  # noqa: E402
import utils  # noqa: E402


class TestPhone:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0700123456", "+996700123456"),
            ("0 700 12-34-56", "+996700123456"),
            ("+996700123456", "+996700123456"),
            ("996700123456", "+996700123456"),
            ("79991234567", "+79991234567"),
            ("89991234567", "+79991234567"),
            ("+491701234567", "+491701234567"),
        ],
    )
    def test_valid(self, raw, expected):
        assert utils.validate_phone(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["", "телефон", "123", "07001234567890123", "+", "0700-abc-456"]
    )
    def test_invalid(self, raw):
        assert utils.validate_phone(raw) is None


class TestName:
    @pytest.mark.parametrize("raw", ["Айгерим", "Анна-Мария", "John Smith", "О'Нил"])
    def test_valid(self, raw):
        assert utils.validate_name(raw) == raw

    @pytest.mark.parametrize("raw", ["A", "", "123", "Вася123", "   ", "<b>hack</b>"])
    def test_invalid(self, raw):
        assert utils.validate_name(raw) is None


class TestEscape:
    def test_tags_are_neutralized(self):
        assert "<a" not in utils.escape('<a href="http://evil">клик</a>')

    def test_plain_text_survives(self):
        assert utils.escape("Привет, как дела?") == "Привет, как дела?"

    def test_none_is_safe(self):
        assert utils.escape(None) == ""


class TestScheduling:
    def test_days_are_workdays_only(self):
        for day in scheduling.available_days():
            assert day.weekday() in config.WORKDAYS

    def test_slots_are_within_working_hours(self):
        days = scheduling.available_days()
        assert days, "должен быть хотя бы один рабочий день"
        for slot in scheduling.day_slots(days[0]):
            assert config.WORK_START_HOUR <= slot.hour < config.WORK_END_HOUR

    def test_past_slots_are_not_bookable(self):
        now = scheduling.now()
        for slot in scheduling.bookable_slots(now.date()):
            assert slot > now

    def test_forged_slot_is_rejected(self):
        fake = scheduling.now().replace(hour=3, minute=17) + timedelta(days=1)
        assert not scheduling.is_valid_slot(fake)

    def test_slots_carry_timezone(self):
        days = scheduling.available_days()
        for slot in scheduling.day_slots(days[0]):
            assert slot.tzinfo is not None


class TestBookingId:
    def test_no_confusable_characters(self):
        for _ in range(200):
            assert not set(utils.generate_booking_id()) & set("O0I1")

    def test_length(self):
        assert len(utils.generate_booking_id()) == 6
