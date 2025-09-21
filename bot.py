import os
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from telebot import types
import pendulum
from flask import Flask, request

# Инициализация Flask приложения
app = Flask(__name__)

# 🔑 Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 🔑 Токен ключ для телеги, хранится в рендере
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")
bot = telebot.TeleBot(TOKEN)

# 🌍 Render hostname (для вебхука)
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if not HOSTNAME:
    raise RuntimeError("RENDER_EXTERNAL_HOSTNAME is not set.")
WEBHOOK_URL = f"https://{HOSTNAME}/webhook"

# 👑 Админ
ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

# 📚 30-дневная программа
TASKS = [
    "День 1: Определи 10 ключевых целей на ближайший год.",
    "День 2: Составь утренний ритуал (вода, зарядка, визуализация).",
    "День 3: Откажись от одной вредной привычки.",
    "День 4: Веди дневник мыслей и благодарностей.",
    "День 5: Составь список из 10 сильных сторон.",
    "День 6: Сделай цифровой детокс на 6 часов.",
    "День 7: Подведи итоги недели, отметь победы.",
    "День 8: Применяй правило Парето 20/80.",
    "День 9: Определи 3 главные приоритеты дня.",
    "День 10: Используй технику Pomodoro (25/5).",
    "День 11: Наведи порядок на рабочем месте.",
    "День 12: Минимизируй отвлекающие факторы.",
    "День 13: Сделай 2 часа глубокой работы.",
    "День 14: Итоги недели: оцени продуктивность.",
    "День 15: Напиши свою миссию и ценности.",
    "День 16: Практикуй публичные мини-выступления.",
    "День 17: Научись говорить «нет».",
    "День 18: Прочитай биографию лидера.",
    "День 19: Сделай доброе дело.",
    "День 20: Визуализируй себя через 5 лет.",
    "День 21: Итоги недели: оцени уверенность.",
    "День 22: Составь план учёбы на 1 год.",
    "День 23: Определи наставника.",
    "День 24: Практикуй вечерний анализ.",
    "День 25: Составь финансовую стратегию.",
    "День 26: Сделай ревизию окружения.",
    "День 27: Поделись знаниями.",
    "День 28: Итоги: составь план на месяц.",
    "День 29: Определи 3 долгосрочные мечты.",
    "День 30: Создай карту жизни."
]

# 🏆 Достижения
ACHIEVEMENTS = {
    5: "🏅 Молодец! 5 дней подряд!",
    10: "🥈 Ты машина! 10 дней без перерыва!",
    20: "🥇 Железная сила воли! 20 дней подряд!",
    30: "👑 Герой челленджа! 30 дней!"
}

# 📦 Подключение к БД
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                day INTEGER DEFAULT 1,
                streak INTEGER DEFAULT 0,
                last_done DATE,
                achievements TEXT[] DEFAULT '{}',
                subscribed BOOLEAN DEFAULT FALSE,
                username TEXT
            );
            """)
            cur.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='last_menu_message_id') THEN ALTER TABLE users ADD COLUMN last_menu_message_id INTEGER; END IF; END $$;")
            conn.commit()
            logging.info("Database schema initialized or verified.")

init_db()

# 📌 Работа с пользователем
def init_user(chat_id, username=None):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO users (chat_id, username, day) VALUES (%s, %s, %s)", (chat_id, username, 1))
                conn.commit()

def get_user(chat_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
            return cur.fetchone()

def update_user(chat_id, **kwargs):
    if not kwargs:
        return
    allowed_fields = {"day", "streak", "last_done", "achievements", "subscribed", "username", "last_menu_message_id"}
    safe_kwargs = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not safe_kwargs:
        logging.warning(f"update_user: no allowed fields to update for {chat_id}: {list(kwargs.keys())}")
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            fields = ", ".join(f"{k} = %s" for k in safe_kwargs.keys())
            values = list(safe_kwargs.values()) + [chat_id]
            cur.execute(f"UPDATE users SET {fields} WHERE chat_id = %s", tuple(values))
            conn.commit()

# 🔄 Получить задание
def get_task(user):
    day = user.get('day') or 1
    idx = max(0, min(len(TASKS)-1, day-1))
    return TASKS[idx]

# 🎯 Проверка достижений
def check_achievements(user):
    unlocked = []
    current_streak = user.get('streak') or 0
    existing = user.get('achievements') or []
    for threshold, text in ACHIEVEMENTS.items():
        str_threshold = str(threshold)
        if current_streak >= threshold and str_threshold not in existing:
            new_achievements = existing + [str_threshold]
            update_user(user['chat_id'], achievements=new_achievements)
            unlocked.append(text)
            existing = new_achievements
    return unlocked

# ⏩ Следующее задание (пользователь нажал "Выполнено")
def next_task(user):
    today = pendulum.now('UTC').date()
    streak = user.get('streak') or 0
    streak += 1
    current_day = user.get('day') or 1
    new_day = current_day + 1
    update_user(user['chat_id'], day=new_day, streak=streak, last_done=today)
    user = get_user(user['chat_id'])
    return get_task(user), check_achievements(user), user

# 🖲 Кнопки
def get_inline_keyboard(user):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("📅 Сегодня", callback_data="today"),
        types.InlineKeyboardButton("✅ Выполнено", callback_data="next")
    )
    keyboard.add(types.InlineKeyboardButton("📊 Статистика", callback_data="stats"))
    keyboard.add(types.InlineKeyboardButton("ℹ Помощь", callback_data="help"))
    keyboard.add(
        types.InlineKeyboardButton(
            "🔔 Подписаться" if not user.get('subscribed', False) else "❌ Отписаться",
            callback_data="subscribe" if not user.get('subscribed', False) else "unsubscribe"
        )
    )
    return keyboard

# === send_menu (устраняет "липкие" клавиши)
def send_menu(chat_id, user, text):
    try:
        fresh_user = get_user(chat_id) or user or {'subscribed': False}
        prev_id = fresh_user.get('last_menu_message_id')
        if prev_id and int(prev_id) > 0:
            try:
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=int(prev_id), reply_markup=None)
            except Exception as e:
                try:
                    bot.delete_message(chat_id, int(prev_id))
                    update_user(chat_id, last_menu_message_id=None)
                except Exception:
                    pass
        msg = bot.send_message(chat_id, text, reply_markup=get_inline_keyboard(fresh_user))
        update_user(chat_id, last_menu_message_id=msg.message_id)
    except Exception as e:
        logging.error(f"send_menu error for {chat_id}: {e}")

# ▶️ /start
@bot.message_handler(commands=['start'])
def start(message):
    init_user(message.chat.id, message.from_user.username)
    user = get_user(message.chat.id)
    send_menu(
        message.chat.id,
        user,
        "Привет 👋 Я твой наставник на 30-дневном пути развития!\n\n"
        "Нажимай кнопки ниже, чтобы получать задания и отмечать выполнение."
    )

# 📊 /stats
@bot.message_handler(commands=['stats'])
def stats(message):
    user = get_user(message.chat.id)
    ach_list = [ACHIEVEMENTS.get(int(x), "") for x in (user.get('achievements') or []) if x.isdigit()]
    ach_text = "🎯 Достижения:\n" + ("\n".join(ach_list) if ach_list else "пока нет")
    send_menu(
        message.chat.id,
        user,
        f"📊 Статистика:\n📅 День: {user.get('day')}/{len(TASKS)}\n🔥 Серия: {user.get('streak') or 0} дней подряд\n{ach_text}"
    )

# 👑 /all_stats (только админ)
@bot.message_handler(commands=['all_stats'])
def all_stats(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.send_message(message.chat.id, "🚫 Команда доступна только администратору.")
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id, username, day, streak FROM users ORDER BY day DESC LIMIT 500;")
            users = cur.fetchall()
    if not users:
        bot.send_message(message.chat.id, "Нет пользователей.")
        return
    text = "👥 Статистика по пользователям (макс 500):\n" + "\n".join(
        f"- {f'@{u['username']}' if u.get('username') else u['chat_id']}: день {u.get('day')}, серия {u.get('streak')} дней"
        for u in users
    )
    bot.send_message(message.chat.id, text)

# 🎛 Обработка кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    chat_id = call.message.chat.id
    init_user(chat_id, call.from_user.username)
    user = get_user(chat_id)
    data = call.data
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.warning(f"Callback error: {e}")
    if data == "today":
        send_menu(chat_id, user, f"📌 Сегодня: {get_task(user)}")
    elif data == "next":
        task, achievements, user = next_task(user)
        text = f"➡ Следующее задание:\n{task}\n\n🔥 Серия: {user.get('streak')} дней\n📅 День {user.get('day')}/{len(TASKS)}"
        send_menu(chat_id, user, text)
        for ach in achievements:
            bot.send_message(chat_id, f"🎉 {ach}")
    elif data == "stats":
        ach_list = [ACHIEVEMENTS.get(int(x), "") for x in (user.get('achievements') or []) if x.isdigit()]
        ach_text = "🎯 Достижения:\n" + ("\n".join(ach_list) if ach_list else "пока нет")
        send_menu(chat_id, user, f"📊 Статистика:\n📅 День: {user.get('day')}/{len(TASKS)}\n🔥 Серия: {user.get('streak') or 0} дней подряд\n{ach_text}")
    elif data == "subscribe":
        update_user(chat_id, subscribed=True)
        user = get_user(chat_id)
        send_menu(chat_id, user, "✅ Напоминания включены! Буду писать в установленное время.")
    elif data == "unsubscribe":
        update_user(chat_id, subscribed=False)
        user = get_user(chat_id)
        send_menu(chat_id, user, "❌ Ты отписался от напоминаний.")
    elif data == "help":
        send_menu(chat_id, user, "ℹ Я помогаю пройти 30-дневную программу совершенствования:\n"
                                "📅 — показать задание на сегодня\n"
                                "✅ — отметить выполнение\n"
                                "📊 — статистика\n"
                                "🔔 — подписка на напоминания\n\n"
                                "🎯 Выполняя задания подряд, ты будешь получать достижения!")

# ⏰ Планировщик (только подписчикам)
def send_scheduled_task():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE subscribed = TRUE;")
            subs = cur.fetchall()
    for user in subs:
        try:
            task = get_task(user)
            text = f"📌 Автоматическое напоминание:\n{task}\n\nЕсли выполнил(а) — открой бот и нажми ✅."
            bot.send_message(user['chat_id'], text)
        except Exception as e:
            logging.error(f"Error in scheduled task for {user['chat_id']}: {e}")

# Регистрация вебхука для Flask
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = telebot.types.Update.de_json(request.get_data(as_text=True))
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Not Found', 404

# Health check для Render
@app.route('/', methods=['GET'])
def health_check():
    return 'OK', 200

# ▶️ Запуск
if __name__ == '__main__':
    # Установка вебхука
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"🔗 Webhook установлен: {WEBHOOK_URL}")

    # Настройка планировщика
    scheduler = BackgroundScheduler()
    REMINDER_HOUR = os.getenv("REMINDER_HOUR", "09:00")
    scheduler.add_job(send_scheduled_task, 'cron', hour=int(REMINDER_HOUR.split(':')[0]), minute=int(REMINDER_HOUR.split(':')[1]))
    scheduler.start()

    # Бесконечный цикл для поддержания процесса
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logging.info("Scheduler and application shut down.")