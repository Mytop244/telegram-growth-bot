# 🤖 Telegram Growth Bot

Бот для Telegram, который собирает статистику и отвечает на команды. Работает на Render с вебхуком.

---

## ⚡ Фичи

- `/today` — статистика за сегодня  
- `/stats` — общая статистика  
- `/help` — помощь по командам  
- `/subscribe` — подписка на уведомления  
- `/next` — следующая запись  

---

## 🛠 Технологии

- Python 3.13  
- Flask / Telebot  
- PostgreSQL (Render Database)  
- Render (Web Service)  

---

## 🚀 Установка и запуск

1. Клонируем репозиторий:  
```bash
git clone <репозиторий>
cd telegram-growth-bot
Устанавливаем зависимости:

bash
Копировать код
pip install -r requirements.txt
Настраиваем переменные окружения в Render:

ini
Копировать код
DATABASE_URL=<твой URL базы данных>
BOT_TOKEN=<токен Telegram бота>
WEBHOOK_URL=https://<твой-домен>.onrender.com/webhook
Деплой на Render (Web Service, Python 3.13).
