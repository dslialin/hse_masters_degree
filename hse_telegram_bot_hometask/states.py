from aiogram.fsm.state import State, StatesGroup

class ProfileState(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()

class FoodState(StatesGroup):
    grams = State()