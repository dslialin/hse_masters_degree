import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import router
from middlewares import LoggingMiddleware
from flask import Flask
import threading
import os

bot = Bot(token=TOKEN)
dp = Dispatcher()

dp.message.middleware(LoggingMiddleware())
dp.include_router(router)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    # Получаем порт от Render (или используем 5000 по умолчанию)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Flask-сервер запускается в отдельном потоке
    threading.Thread(target=run_flask).start()
    # Основной поток — это работа Telegram-бота
    asyncio.run(main())


# import asyncio
# from aiogram import Bot, Dispatcher
# from config import TOKEN
# from handlers import router
# from middlewares import LoggingMiddleware

# bot = Bot(token=TOKEN)
# dp = Dispatcher()

# dp.message.middleware(LoggingMiddleware())
# dp.include_router(router)

# async def main():
#     print("Бот запущен")
#     await dp.start_polling(bot)

# if __name__ == "__main__":
#     asyncio.run(main())
