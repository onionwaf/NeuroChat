# NeuroChattingBot

Desktop application for automating Telegram communication and promotion.  
It connects **multiple Telegram accounts** with **Mistral AI**,  
so you can automatically reply in chats and promote channels, groups, and projects.

[🇷🇺 Читать на русском](#на-русском)

---

## 🤔 Who is this app for?

This app will be useful for:
- **SMM specialists** — to promote brands on Telegram.
- **Marketers** — to manage multiple accounts at once.
- **Channel and group admins** — to automate communication with subscribers.
- **Promotion managers** — to quickly find new chats and interact there with AI replies.
- **Anyone** — who wants to save time and simplify Telegram work.

---

## ✨ Features

### 🔑 Multi-account
- Connect multiple Telegram accounts.  
- Login via phone number (confirmation code).  
- Or import `.session` files.  
- Turn accounts on/off anytime.  

### 🔍 Chat search
- Find Telegram chats by keywords.  
- Join chats directly from the app.  
- Manage a list of active chats.  

### 🛡 Message filters
- Reply only to “valid” messages:  
  - longer than a given number of words;  
  - in the correct language (RU/EN);  
  - unique (anti-spam).  
- Enable/disable filters in settings.  

### ⚡ Triggers
- Create trigger words/phrases (e.g., *buy*, *support*, *help*).  
- If a message matches → bot replies.  
- Separate triggers for each chat.  

### 🎭 Reply styles (prompts)
- Choose how the bot talks:  
  - friendly,  
  - expert,  
  - humorous,  
  - or your custom style.  

### 🤖 Mistral AI
- Uses the **official Mistral API**.  
- AI generates a reply in the chosen style.  
- Configurable timeout (e.g., max 1 reply/minute).  

### 💬 Auto replies
- Replies are sent instantly in chats.  
- Each account can work in its own chats.  
- Logging of all actions (what and where was sent).  

### 🖥 User-friendly interface (PyQt6)
Tabs in the main window:  
- **Accounts** — add/import/remove, turn on/off.  
- **Chats** — search, join, set triggers.  
- **AI (Mistral)** — enter API key, choose style.  
- **Settings** — filters, timeouts, auto-start.  
- **Logs** — real-time activity.  

---

## 🚀 Installation

1. Install Python **3.11+**.  
2. Clone the project and open the folder.  
3. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` → `.env` and add your Mistral API key.  
5. Run the app:  
   ```bash
   python run.py
   ```

---

## ⬇️ Download (Windows)

You don’t need to install Python to use the app.  
A ready-to-use **Windows .exe version** is available in the [Releases section](../../releases).  
Just download the `.exe` file and run it.

## 🔑 Get your Mistral API key

To use AI, you need a **Mistral API key**:  
- Register here: [https://console.mistral.ai/](https://console.mistral.ai/)  
- Go to **API Keys** section.  
- Create a key and copy it.  
- Paste this api in settings "AI mistral`

---

## ℹ️ About me
⚠️ I am **not a professional programmer**.  
This app was created with the help of **ChatGPT-5**.  
You can use this project to **promote your own projects on Telegram**.  

---

## 📜 License
License: **Non-Commercial Open License 1.0 (NCOL-1.0)**.  
You may use, modify, and share the code, but **commercial use is forbidden**.  

---

# На русском

## 📌 Описание
**NeuroChattingBot** — это десктопное приложение для автоматизации общения и продвижения в Telegram.  
Оно соединяет **несколько Telegram-аккаунтов** и **искусственный интеллект Mistral AI**,  
чтобы автоматически отвечать в чатах и помогать продвигать каналы, группы и проекты.  

## 🤔 Кому пригодится?
- **SMM-специалистам** — для продвижения брендов.  
- **Маркетологам** — для работы с несколькими аккаунтами.  
- **Админам каналов и чатов** — для общения с подписчиками.  
- **Продвиженцам** — для поиска новых чатов и ответов через ИИ.  
- **Всем** — кто хочет упростить работу в Telegram.  

## ✨ Основные возможности
- 🔑 Подключение нескольких аккаунтов (вход по номеру или импорт `.session`).  
- 🔍 Поиск чатов по ключевым словам, вступление прямо из программы.  
- 🛡 Фильтры сообщений: длина, язык, уникальность.  
- ⚡ Триггеры — слова/фразы, при которых бот отвечает.  
- 🎭 Стили ответов: дружеский, экспертный, шуточный, кастомный.  
- 🤖 Подключение к **Mistral API** для генерации ответов.  
- 💬 Автоматические ответы от разных аккаунтов, ведение логов.  
- 🖥 Удобный интерфейс на PyQt6 с вкладками (аккаунты, чаты, AI, настройки, логи).  

## 🚀 Установка и запуск
1. Установите Python 3.11+.  
2. Склонируйте проект и перейдите в папку.  
3. Установите зависимости:  
   ```bash
   pip install -r requirements.txt
   ```
4. Скопируйте `.env.example` → `.env` и вставьте свой ключ Mistral API.  
5. Запустите:  
   ```bash
   python run.py
   ```

## ⬇️ Скачать (Windows)

Не нужно устанавливать Python, чтобы пользоваться программой.  
Готовая **Windows .exe версия** доступна в разделе [Releases](../../releases).  
Просто скачайте `.exe` файл и запустите его.

## 🔑 Где взять Mistral API ключ?
- Зарегистрируйтесь на [https://console.mistral.ai/](https://console.mistral.ai/)  
- Перейдите в раздел **API Keys**.  
- Создайте ключ и скопируйте его.  
- Вставьте его в программе в разделе "AI mistral".  

## ℹ️ Обо мне
⚠️ Я **не программист**.  
Это приложение сделано с помощью **ChatGPT-5**.  
Вы можете использовать его для **продвижения своих проектов в Telegram**.  

## 📜 Лицензия
Лицензия: **Non-Commercial Open License 1.0 (NCOL-1.0)**.  
Код можно использовать, изменять и распространять, но **нельзя использовать в коммерческих целях**.  
