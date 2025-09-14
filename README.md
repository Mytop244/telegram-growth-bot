# 🤖 Telegram Growth Bot

Бот для Telegram, который собирает статистику и отвечает на команды. Работает на Render с вебхуком.

---

## ⚡ Фичи

* `/today` — статистика за сегодня
* `/stats` — общая статистика
* `/help` — помощь по командам
* `/subscribe` — подписка на уведомления
* `/next` — следующая запись

---

## 🛠 Технологии

* Python 3.13
* Flask / Telebot
* PostgreSQL (Render Database)
* Render (Web Service)

---

## 🚀 Установка и запуск

1. Клонируем репозиторий:

```bash
git clone <репозиторий>
cd telegram-growth-bot
```

2. Устанавливаем зависимости:

```bash
pip install -r requirements.txt
```

3. Настраиваем переменные окружения в Render:

```
DATABASE_URL=<твой URL базы данных>
BOT_TOKEN=<токен Telegram бота>
WEBHOOK_URL=https://<твой-домен>.onrender.com/webhook
```

4. Деплой на Render (Web Service, Python 3.13).

---

## 🌙 Не засыпает

Чтобы Render Web Service не уходил в сон, используем **UptimeRobot**:

* URL для пинга: `https://<твой-домен>.onrender.com`
* Интервал: 5 минут

---

## 📡 Webhook

Webhook автоматически устанавливается при запуске:

```
https://<твой-домен>.onrender.com/webhook
```

---

## 🐞 Логи

* Логи выводятся в Render Dashboard
* Ошибки с Telegram API (429, 400) фиксировать через задержки и повторные запросы

---

## 🔗 Ссылки

* [Render Docs](https://render.com/docs)
* [UptimeRobot](https://uptimerobot.com/)

---

## ⚠️ Примечания

* Free-tier Render спит через 15 минут без трафика
* Cron Job платный на Render, используем UptimeRobot
