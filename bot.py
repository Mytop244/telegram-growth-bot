import os
import telebot
import schedule
import time
import threading
import logging
import http.server
import socketserver
import psycopg2
from psycopg2.extras import RealDictCursor
from telebot import types
from datetime import datetime, timedelta

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
    # Если таблицы ещё нет, создадим с колонкой last_menu_message_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id BIGINT PRIMARY KEY,
        day INTEGER DEFAULT 1,
        streak INTEGER DEFAULT 0,
        last_done DATE,
        achievements TEXT[] DEFAULT '{}',
        subscribed BOOLEAN DEFAULT FALSE,
        username TEXT,
        last_menu_message_id INTEGER
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# 📌 Работа с пользователем
def init_user(chat_id, username=None):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
        user = cur.fetchone()
        if not user:
            cur.execute("INSERT INTO users (chat_id, username, day) VALUES (%s, %s, %s)", (chat_id, username, 1))
            conn.commit()
    finally:
        cur.close()
        conn.close()

def get_user(chat_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
        user = cur.fetchone()
        return user
    finally:
        cur.close()
        conn.close()

def update_user(chat_id, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    cur = conn.cursor()
    try:
        fields = ", ".join([f"{k} = %s" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(chat_id)
        cur.execute(f"UPDATE users SET {fields} WHERE chat_id = %s", tuple(values))
        conn.commit()
    finally:
        cur.close()
        conn.close()

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
    today = datetime.utcnow().date()
    last_done = user.get('last_done')
    streak = user.get('streak') or 0

    if last_done:
        if today == last_done + timedelta(days=1):
            streak += 1
        elif today == last_done:
            pass
        else:
            streak = 1
    else:
        streak = 1

    current_day = user.get('day') or 1
    new_day = current_day + 1 if current_day < len(TASKS) else current_day
    update_user(user['chat_id'], day=new_day, streak=streak, last_done=today)
    user = get_user(user['chat_id'])
    return get_task(user), check_achievements(user), user

# 🖲 Кнопки
def get_inline_keyboard(user):
    if not user:
        user = {'subscribed': False}
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("📅 Сегодня", "today"),
        ("✅ Выполнено", "next"),
        ("📊 Статистика", "stats"),
        ("ℹ Помощь", "help"),
        ("❌ Отписаться" if user.get('subscribed') else "🔔 Подписаться", "unsubscribe" if user.get('subscribed') else "subscribe")
    ]
    keyboard.add(
        types.InlineKeyboardButton(buttons[0][0].ljust(12, '\u00A0'), callback_data=buttons[0][1]),
        types.InlineKeyboardButton(buttons[1][0].ljust(12, '\u00A0'), callback_data=buttons[1][1])
    )
    keyboard.add(
        types.InlineKeyboardButton(buttons[2][0].ljust(12, '\u00A0'), callback_data=buttons[2][1]),
        types.InlineKeyboardButton(buttons[3][0].ljust(12, '\u00A0'), callback_data=buttons[3][1])
    )
    keyboard.add(
        types.InlineKeyboardButton(buttons[4][0].ljust(12, '\u00A0'), callback_data=buttons[4][1])
    )
    return keyboard

# === Новая функция: send_menu ===
def send_menu(chat_id, user, text):
    """
    Отправляет меню пользователю:
    - очищает клавиатуру у предыдущего меню (если есть),
    - отправляет новое сообщение с клавиатурой,
    - сохраняет message_id нового меню в users.last_menu_message_id.
    """
    try:
        prev_id = user.get('last_menu_message_id')
        if prev_id:
            try:
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=prev_id, reply_markup=None)
            except Exception as e:
                # часто сообщение могло быть удалено пользователем -> игнорируем
                logging.debug(f"Can't clear previous menu {prev_id} for {chat_id}: {e}")

        msg = bot.send_message(chat_id, text, reply_markup=get_inline_keyboard(user))
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
    ach_list = []
    for x in (user.get('achievements') or []):
        try:
            ach_list.append(ACHIEVEMENTS.get(int(x), ""))
        except Exception:
            pass
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

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users ORDER BY day DESC;")
        users = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    if not users:
        bot.send_message(message.chat.id, "Нет пользователей.")
        return

    text = "👥 Статистика по всем пользователям:\n"
    for u in users:
        uname = f"@{u['username']}" if u.get('username') else u['chat_id']
        text += f"- {uname}: день {u.get('day')}, серия {u.get('streak')} дней\n"
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
        ach_list = []
        for x in (user.get('achievements') or []):
            try:
                ach_list.append(ACHIEVEMENTS.get(int(x), ""))
            except Exception:
                pass
        ach_text = "🎯 Достижения:\n" + ("\n".join(ach_list) if ach_list else "пока нет")
        send_menu(
            chat_id,
            user,
            f"📊 Статистика:\n📅 День: {user.get('day')}/{len(TASKS)}\n🔥 Серия: {user.get('streak') or 0} дней подряд\n{ach_text}"
        )

    elif data == "subscribe":
        update_user(chat_id, subscribed=True)
        user = get_user(chat_id)
        send_menu(chat_id, user, "✅ Напоминания включены! Буду писать в установленное время.")

    elif data == "unsubscribe":
        update_user(chat_id, subscribed=False)
        user = get_user(chat_id)
        send_menu(chat_id, user, "❌ Ты отписался от напоминаний.")

    elif data == "help":
        send_menu(
            chat_id,
            user,
            "ℹ Я помогаю пройти 30-дневную программу совершенствования:\n"
            "📅 — показать задание на сегодня\n"
            "✅ — отметить выполнение\n"
            "📊 — статистика\n"
            "🔔 — подписка на напоминания\n\n"
            "🎯 Выполняя задания подряд, ты будешь получать достижения!"
        )

# ⏰ Планировщик (только подписчикам)
def schedule_checker():
    while True:
        schedule.run_pending()
        time.sleep(30)

def send_scheduled_task():
    """
    Отправляет напоминание о текущем задании подписчикам, но НЕ помечает задание как выполненное.
    И НЕ прикрепляет клавиатуру (чтобы не создавать лишних меню).
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE subscribed = TRUE;")
        subs = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    for user in subs:
        try:
            task = get_task(user)
            text = f"📌 Автоматическое напоминание:\n{task}\n\nЕсли выполнил(а) — открой бот и нажми ✅."
            bot.send_message(user['chat_id'], text)
        except Exception as e:
            logging.error(f"Error in scheduled task for {user['chat_id']}: {e}")

# 🌍 Webhook сервер
class Handler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Hello, I am alive!")

    def do_POST(self):
        if self.path == "/webhook":
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length)
            try:
                update = telebot.types.Update.de_json(body.decode("utf-8"))
            except Exception as e:
                logging.error(f"Failed to parse update body: {e}")
                self.send_response(400)
                self.end_headers()
                return

            if update.message:
                user = update.message.from_user
                logging.info(f"📩 Сообщение от @{user.username or user.id}: {update.message.text}")
            elif update.callback_query:
                user = update.callback_query.from_user
                logging.info(f"🔘 Callback от @{user.username or user.id}: {update.callback_query.data}")

            try:
                bot.process_new_updates([update])
            except Exception as e:
                logging.error(f"❌ Ошибка при обработке апдейта: {e}")

            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def start_web_server():
    port = int(os.getenv("PORT", 10000))
    with ReusableTCPServer(("", port), Handler) as httpd:
        logging.info(f"✅ Webhook server running on port {port}")
        httpd.serve_forever()

# ▶️ Запуск
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"🔗 Webhook установлен: {WEBHOOK_URL}")

    REMINDER_HOUR = os.getenv("REMINDER_HOUR", "09:00")
    schedule.every().day.at(REMINDER_HOUR).do(send_scheduled_task)
    threading.Thread(target=schedule_checker, daemon=True).start()

    start_web_server()