from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types.input_file import FSInputFile
import aiohttp
import matplotlib.pyplot as plt
import os
from dotenv import load_dotenv
load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

router = Router()

users_data = {}

def generate_progress_graph(data, title, x_label, y_label, filename):
    fig, ax = plt.subplots()
    ax.bar(data.keys(), data.values(), color='blue', alpha=0.7)
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)
    plt.savefig(filename)
    plt.close(fig)

async def get_weather_temp(city, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["main"]["temp"]
    return 20

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Я помогу рассчитать воду, калории и вести учёт.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "/set_profile – Настройка профиля\n"
        "/log_water <количество> – Записать воду\n"
        "/log_food <продукт> – Записать еду\n"
        "/log_workout <тип> <минуты> – Записать тренировку\n"
        "/check_progress – Прогресс за сегодня\n"
        "/show_graphs – Показать графики прогресса\n"
    )
    await message.answer(text)

@router.message(Command("set_profile"))
async def set_profile_start(message: Message, state: FSMContext):
    await message.answer("Введите ваш вес (кг):")
    await state.set_state("weight")

@router.message(StateFilter("weight"))
async def set_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await message.answer("Введите ваш рост (см):")
    await state.set_state("height")

@router.message(StateFilter("height"))
async def set_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.answer("Введите ваш возраст:")
    await state.set_state("age")

@router.message(StateFilter("age"))
async def set_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Сколько минут активности в день?")
    await state.set_state("activity")

@router.message(StateFilter("activity"))
async def set_activity(message: Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("В каком городе вы находитесь?")
    await state.set_state("city")

@router.message(StateFilter("city"))
async def set_city(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    city = message.text
    try:
        weight = float(data["weight"])
        height = float(data["height"])
        age = float(data["age"])
        activity = float(data["activity"])
        temp = await get_weather_temp(city, OPENWEATHER_API_KEY)
        base_water = weight * 30
        extra_for_activity = (activity // 30) * 500
        hot_bonus = 500 if temp > 25 else 0
        water_goal = int(base_water + extra_for_activity + hot_bonus)
        cal_base = (10 * weight) + (6.25 * height) - (5 * age)
        cal_activity = 200 if activity < 30 else 300 if activity < 60 else 400
        calorie_goal = int(cal_base + cal_activity)
        users_data[user_id] = {
            "weight": weight,
            "height": height,
            "age": age,
            "activity": activity,
            "city": city,
            "water_goal": water_goal,
            "calorie_goal": calorie_goal,
            "logged_water": 0,
            "logged_calories": 0,
            "burned_calories": 0
        }
        await message.answer(f"Профиль сохранён. Вода: {water_goal} мл, калорий: {calorie_goal}")
    except:
        await message.answer("Ошибка в данных, попробуйте заново /set_profile")
    await state.clear()

@router.message(Command("log_water"))
async def log_water(message: Message):
    user_id = message.from_user.id
    if user_id not in users_data:
        await message.answer("Сначала настройте профиль /set_profile")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите количество воды, например /log_water 200")
        return
    try:
        amount = float(args[1])
        users_data[user_id]["logged_water"] += amount
        left_water = users_data[user_id]["water_goal"] - users_data[user_id]["logged_water"]
        if left_water < 0:
            left_water = 0
        await message.answer(f"Записано {amount} мл воды. Осталось: {left_water} мл.")
    except:
        await message.answer("Некорректный ввод, пример: /log_water 300")

@router.message(Command("log_food"))
async def log_food_step1(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_data:
        await message.answer("Сначала настройте профиль /set_profile")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажите продукт, например /log_food банан")
        return
    product_name = args[1]
    async with aiohttp.ClientSession() as session:
        url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                products = data.get('products', [])
                if products:
                    p = products[0]
                    cals = p.get('nutriments', {}).get('energy-kcal_100g', 0)
                    name = p.get('product_name', 'Неизвестно')
                    await state.update_data(prod_name=name, cals=cals)
                    await message.answer(f"{name} — {cals} ккал на 100 г. Сколько грамм вы съели?")
                    await state.set_state("grams")
                    return
    await message.answer("Не удалось найти информацию о продукте.")

@router.message(StateFilter("grams"))
async def log_food_step2(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    try:
        grams = float(message.text)
        cals_100g = data["cals"]
        total = (grams * cals_100g) / 100
        users_data[user_id]["logged_calories"] += total
        await message.answer(f"Записано: {round(total,1)} ккал.")
    except:
        await message.answer("Ошибка при записи, введите число граммов ещё раз")
        return
    await state.clear()

@router.message(Command("log_workout"))
async def log_workout(message: Message):
    user_id = message.from_user.id
    if user_id not in users_data:
        await message.answer("Сначала настройте профиль /set_profile")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Пример: /log_workout бег 30")
        return
    workout_type = args[1]
    try:
        minutes = float(args[2])
        burned = minutes * 10
        users_data[user_id]["burned_calories"] += burned
        extra_water = int((minutes // 30) * 200)
        if extra_water:
            await message.answer(f"{workout_type} {minutes} мин — {int(burned)} ккал. Дополнительно выпейте {extra_water} мл воды.")
        else:
            await message.answer(f"{workout_type} {minutes} мин — {int(burned)} ккал.")
    except:
        await message.answer("Пример: /log_workout бег 30")

@router.message(Command("check_progress"))
async def check_progress(message: Message):
    user_id = message.from_user.id
    if user_id not in users_data:
        await message.answer("Сначала настройте профиль /set_profile")
        return
    w = users_data[user_id]["logged_water"]
    wg = users_data[user_id]["water_goal"]
    c = users_data[user_id]["logged_calories"]
    cg = users_data[user_id]["calorie_goal"]
    b = users_data[user_id]["burned_calories"]
    balance = c - b
    text = (
        f"Вода:\nВыпито: {int(w)} мл из {wg} мл\n"
        f"Осталось: {max(wg - w, 0)} мл\n\n"
        f"Калории:\nПотреблено: {int(c)} ккал из {cg} ккал\n"
        f"Сожжено: {int(b)} ккал\n"
        f"Баланс: {int(balance)} ккал"
    )
    await message.answer(text)

@router.message(Command("show_graphs"))
async def show_graphs(message: Message):
    user_id = message.from_user.id
    if user_id not in users_data:
        await message.answer("Сначала настройте профиль /set_profile.")
        return

    water_data = {
        "Выпито": users_data[user_id]["logged_water"],
        "Цель": users_data[user_id]["water_goal"]
    }
    calorie_data = {
        "Потреблено": users_data[user_id]["logged_calories"],
        "Цель": users_data[user_id]["calorie_goal"],
        "Сожжено": users_data[user_id]["burned_calories"]
    }

    generate_progress_graph(water_data, "Прогресс по воде", "Параметр", "Мл", "water_progress.png")
    generate_progress_graph(calorie_data, "Прогресс по калориям", "Параметр", "Ккал", "calorie_progress.png")

    try:
        # Используем путь к файлу для FSInputFile
        water_graph_file = FSInputFile("water_progress.png")
        calorie_graph_file = FSInputFile("calorie_progress.png")

        await message.answer_photo(photo=water_graph_file, caption="Ваш прогресс по воде 🥤")
        await message.answer_photo(photo=calorie_graph_file, caption="Ваш прогресс по калориям 🍖")
    except Exception as e:
        await message.answer(f"Ошибка при отправке графиков: {e}")