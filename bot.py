import os
import random
import telebot
from flask import Flask, request
import logging
from logging.handlers import RotatingFileHandler
import json
from datetime import datetime, timedelta
import time
import signal
import sys
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
try:
    import pkg_resources
    PKG_RESOURCES_AVAILABLE = True
except ImportError:
    PKG_RESOURCES_AVAILABLE = False
import flask

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', maxBytes=1000000, backupCount=5)
    ]
)
logger = logging.getLogger(__name__)

# Логирование версий библиотек
if PKG_RESOURCES_AVAILABLE:
    try:
        telebot_version = pkg_resources.get_distribution("pyTelegramBotAPI").version
        logger.debug(f"Версия pyTelegramBotAPI: {telebot_version}")
    except pkg_resources.DistributionNotFound:
        logger.debug("Версия pyTelegramBotAPI: неизвестна (pyTelegramBotAPI не установлен)")
else:
    logger.debug("Версия pyTelegramBotAPI: неизвестна (pkg_resources не доступен)")
logger.debug(f"Версия Flask: {flask.__version__}")

# Проверка переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = os.getenv("PORT", 10000)

logger.debug(f"Переменные окружения: BOT_TOKEN={'<скрыт>' if TOKEN else None}, "
             f"RENDER_EXTERNAL_URL={RENDER_EXTERNAL_URL}, PORT={PORT}")

if not TOKEN:
    logger.error("BOT_TOKEN не задан в переменных окружения")
    raise ValueError("BOT_TOKEN не задан")
if not RENDER_EXTERNAL_URL:
    logger.error("RENDER_EXTERNAL_URL не задан в переменных окружения")
    raise ValueError("RENDER_EXTERNAL_URL не задан")

# Инициализация бота и Flask
try:
    bot = telebot.TeleBot(TOKEN)
    logger.info("Бот успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {str(e)}")
    raise

app = Flask(__name__)
logger.info("Flask приложение инициализировано")

# Загрузка советов
advices = []
try:
    if os.path.exists("advices.txt"):
        with open("advices.txt", encoding="utf-8") as f:
            advices = [line.strip() for line in f if line.strip()]
            logger.info(f"Загружено {len(advices)} советов из advices.txt: {advices[:3]}...")
    else:
        advices = [
            "Пей больше воды",
            "Выходи гулять каждый день",
            "Высыпайся — сон лечит всё",
            "Веди дневник благодарности",
            "Учись чему-то новому каждый день",
            "Делай маленькие шаги к большой цели",
            "Меньше соцсетей — больше реальной жизни",
            "Занимайся спортом хотя бы 10 минут в день",
            "Медитируй и отдыхай от стресса",
            "Помогай другим — добро возвращается",
        ]
        logger.info(f"Файл advices.txt не найден, используются стандартные советы ({len(advices)}): {advices[:3]}...")
except Exception as e:
    logger.error(f"Ошибка при загрузке advices.txt: {str(e)}")
    raise

# Смайлы
emojis = ["🌟", "✨", "🔥", "💡", "🌈", "💖", "🌞", "🍀", "⚡", "🌊"]
logger.debug(f"Загружено {len(emojis)} эмодзи: {emojis}")

# Обработчик сигналов завершения
def signal_handler(sig, frame):
    logger.info(f"Получен сигнал завершения: {signal.Signals(sig).name}")
    logger.info("Завершение работы приложения")
    try:
        bot.remove_webhook()
        logger.info("Вебхук удален перед завершением")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука перед завершением: {str(e)}")
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        logger.debug(f"Системные метрики перед завершением: память={process.memory_info().rss / 1024 / 1024:.2f} МБ")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Хэндлеры
@bot.message_handler(commands=["start"])
def start(msg):
    start_time = time.time()
    logger.info(f"Получена команда /start от user_id={msg.from_user.id} (@{msg.from_user.username}), "
                f"chat_id={msg.chat.id}, message_id={msg.message_id}")
    try:
        response = bot.reply_to(msg, "Привет! Я бот-советчик 🧙‍♂️\nНапиши /advice, и я дам совет!")
        logger.debug(f"Ответ на /start отправлен: message_id={response.message_id}, "
                     f"время выполнения: {time.time() - start_time:.3f} сек")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа на /start: {str(e)}")

@bot.message_handler(commands=["advice"])
def advice(msg):
    start_time = time.time()
    logger.info(f"Получена команда /advice от user_id={msg.from_user.id} (@{msg.from_user.username}), "
                f"chat_id={msg.chat.id}, message_id={msg.message_id}")
    try:
        if random.randint(1, 5) == 1:
            text = random.choice(emojis)
            logger.debug(f"Выбран только эмодзи: {text}")
        else:
            advice_text = random.choice(advices)
            emoji = random.choice(emojis)
            text = f"{advice_text} {emoji}"
            logger.debug(f"Выбран совет: {text}")
        response = bot.reply_to(msg, text)
        logger.debug(f"Ответ на /advice отправлен: message_id={response.message_id}, "
                     f"время выполнения: {time.time() - start_time:.3f} сек")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа на /advice: {str(e)}")

@bot.message_handler(content_types=["text"])
def handle_text(msg):
    start_time = time.time()
    logger.info(f"Получено текстовое сообщение от user_id={msg.from_user.id} (@{msg.from_user.username}), "
                f"chat_id={msg.chat.id}, message_id={msg.message_id}, текст: {msg.text}")
    try:
        response = bot.reply_to(msg, "Я понимаю только команды /start и /advice 😊")
        logger.debug(f"Ответ на текстовое сообщение отправлен: message_id={response.message_id}, "
                     f"время выполнения: {time.time() - start_time:.3f} сек")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа на текстовое сообщение: {str(e)}")

@app.route("/webhook", methods=["POST"])
def webhook():
    start_time = time.time()
    logger.debug(f"Получен запрос на /webhook, headers: {dict(request.headers)}")
    try:
        json_str = request.get_data().decode("utf-8")
        logger.debug(f"Входящее обновление: {json_str}")
        update = telebot.types.Update.de_json(json_str)
        if update is None:
            logger.error("Не удалось декодировать обновление")
            return "ok", 200
        message_info = None
        chat_info = None
        if update.message:
            message_info = {
                "message_id": update.message.message_id,
                "text": update.message.text,
                "from": {
                    "id": update.message.from_user.id,
                    "username": update.message.from_user.username,
                    "first_name": update.message.from_user.first_name
                },
                "date": update.message.date
            }
            if update.message.chat:
                chat_info = {
                    "id": update.message.chat.id,
                    "type": update.message.chat.type,
                    "title": update.message.chat.title if hasattr(update.message.chat, "title") else None
                }
        logger.info(f"Обновление успешно декодировано: update_id={update.update_id}, "
                    f"message={message_info}, chat={chat_info}")
        bot.process_new_updates([update])
        logger.debug(f"Обновление обработано, время выполнения: {time.time() - start_time:.3f} сек")
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {str(e)}")
        return "ok", 200

@app.route("/", methods=["GET"])
def index():
    logger.debug(f"Получен запрос на /, headers: {dict(request.headers)}")
    return "Бот работает!", 200

@app.route("/test", methods=["POST"])
def test():
    start_time = time.time()
    logger.debug(f"Получен тестовый запрос на /test, headers: {dict(request.headers)}")
    try:
        data = request.get_data().decode("utf-8")
        logger.info(f"Тестовый запрос: {data}")
        logger.debug(f"Тестовый запрос обработан, время выполнения: {time.time() - start_time:.3f} сек")
        return "Тест OK", 200
    except Exception as e:
        logger.error(f"Ошибка при обработке тестового запроса: {str(e)}")
        return "error", 500

# Новый эндпоинт для проверки вебхука
@app.route("/ping", methods=["GET"])
def ping():
    try:
        webhook_info = bot.get_webhook_info()
        data = webhook_info.to_dict()
        logger.info(f"Проверка вебхука через /ping: {data}")
        return flask.jsonify({
            "status": "ok",
            "webhook_info": data
        }), 200
    except Exception as e:
        logger.error(f"Ошибка при получении webhook info через /ping: {str(e)}")
        return flask.jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    logger.info("Запуск приложения")
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        logger.debug(f"Системные метрики: память={process.memory_info().rss / 1024 / 1024:.2f} МБ")

    try:
        webhook_info = bot.get_webhook_info()
        logger.info(f"Текущее состояние вебхука: {webhook_info.to_dict()}")
        expected_webhook = f"{RENDER_EXTERNAL_URL}/webhook"
        if webhook_info.url != expected_webhook:
            logger.warning(f"Вебхук не соответствует ожидаемому URL: текущий={webhook_info.url}, "
                           f"ожидаемый={expected_webhook}")
    except Exception as e:
        logger.error(f"Ошибка при получении webhook info: {str(e)}")

    WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"
    logger.debug(f"WEBHOOK_URL: {WEBHOOK_URL}")

    try:
        bot.remove_webhook()
        logger.info("Старый вебхук успешно удален")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {str(e)}")

    try:
        result = bot.set_webhook(url=WEBHOOK_URL)
        if result:
            logger.info(f"Вебхук успешно установлен: {WEBHOOK_URL}")
            webhook_info = bot.get_webhook_info()
            logger.debug(f"Проверка после установки: {webhook_info.to_dict()}")
        else:
            logger.error("Не удалось установить вебхук")
    except Exception as e:
        logger.error(f"Ошибка при установке вебхука: {str(e)}")
        raise

    try:
        logger.info(f"Запуск Flask сервера на 0.0.0.0:{PORT}")
        app.run(host="0.0.0.0", port=int(PORT))
    except Exception as e:
        logger.error(f"Ошибка при запуске Flask сервера: {str(e)}")
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            logger.debug(f"Системные метрики перед завершением: память={process.memory_info().rss / 1024 / 1024:.2f} МБ")
        raise
