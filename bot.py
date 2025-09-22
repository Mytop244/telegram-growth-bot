import telebot
import random
import os

# Получаем токен из переменной окружения (удобно для Render/Heroku)
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Список советов
advices = [
    "Пей больше воды 💧",
    "Выходи гулять каждый день 🚶",
    "Высыпайся — сон лечит всё 😴",
    "Веди дневник благодарности 📓",
    "Учись чему-то новому каждый день 📚",
    "Делай маленькие шаги к большой цели 🎯",
    "Меньше соцсетей — больше реальной жизни 🌱",
    "Занимайся спортом хотя бы 10 минут в день 🏋️",
    "Медитируй и отдыхай от стресса 🧘",
    "Помогай другим — добро возвращается ❤️",
]

# Команда /start
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Привет! Я бот-советчик 🧙‍♂️\nНапиши /advice, и я дам совет!")

# Команда /advice
@bot.message_handler(commands=["advice"])
def advice(message):
    bot.reply_to(message, random.choice(advices))

# Запуск (long polling)
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
