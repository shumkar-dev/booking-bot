from aiogram.fsm.state import State, StatesGroup


class Booking(StatesGroup):
    service = State()
    day = State()
    slot = State()
    name = State()
    phone = State()
    confirm = State()


class Chat(StatesGroup):
    client_waiting = State()
    admin_writing = State()
