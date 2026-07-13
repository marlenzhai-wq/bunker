"""FSM күйлері."""
from aiogram.fsm.state import State, StatesGroup


class StartGameStates(StatesGroup):
    waiting_for_places = State()


class AddHostStates(StatesGroup):
    waiting_for_id = State()
