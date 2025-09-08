# NeuroChat (working title)

Desktop AI chat client with a PyQt6 GUI. Integrates Mistral API and optional Telegram via Telethon.

[🇷🇺 Читать на русском](#на-русском)

---

## Features
- Multi-tab PyQt6 GUI (Chats, AI, Accounts, Settings, Logs, ...)
- Mistral API integration
- Telegram via Telethon
- Theming (dark.qss)
- Logging, filters, prompts, triggers

## Getting Started

### Prerequisites
- Python 3.11+
- Windows/macOS/Linux

### Setup
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Fill your keys: MISTRAL_API_KEY, TELEGRAM_API_ID, TELEGRAM_API_HASH, etc.

python run.py
```

## Configuration
Environment variables are loaded from `.env` (via `python-dotenv`).  
Do **NOT** commit real secrets.  
See `.env.example` for supported variables.

## Build (Windows EXE)
We use PyInstaller.

Quick build:
```powershell
pip install pyinstaller
pyinstaller run.py --name NeuroChat --windowed --onefile ^
  --add-data "theme/dark.qss;theme"
```
The EXE will be in `dist/`.

Tips:
- Add extra resource folders with `--add-data`.
- If dynamic imports are missed, use `.spec` (see `neurochat.spec`).

## CI: GitHub Actions Release
On tag push like `v1.0.0`, CI builds the Windows exe and attaches it to the GitHub Release.  
Workflow file: `.github/workflows/release.yml`.

## License
This repository uses **Non-Commercial Open License 1.0 (NCOL-1.0)** — you can use, modify, and distribute the source, but **commercial use is not permitted**.  
See [LICENSE](LICENSE) for full text.

---

# На русском

## 📌 Описание
NeuroChat — это десктопный чат-клиент с графическим интерфейсом на PyQt6.  
Поддерживает работу с **Mistral API** и (опционально) **Telegram через Telethon**.  

## 🚀 Возможности
- Многооконный интерфейс (Чаты, AI, Аккаунты, Настройки, Логи и т. д.)
- Интеграция с Mistral API
- Поддержка Telegram (через Telethon)
- Темы оформления (например, `dark.qss`)
- Логирование, фильтры, промпты, триггеры

## 🛠 Установка и запуск
1. Установи Python 3.11+.  
2. Склонируй репозиторий и перейди в папку:  
   ```bash
   git clone https://github.com/<username>/neurochat.git
   cd neurochat
   ```
3. Создай виртуальное окружение и установи зависимости:  
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1  # Windows
   # source .venv/bin/activate  # Linux/macOS

   pip install -r requirements.txt
   ```
4. Скопируй `.env.example` → `.env` и пропиши свои ключи (Mistral, Telegram).  
5. Запусти приложение:  
   ```bash
   python run.py
   ```

## ⚙️ Конфигурация
Все настройки хранятся в `.env` (через библиотеку `python-dotenv`).  
Файл `.env` никогда не нужно коммитить!  
Смотри `.env.example` для примера.

## 📦 Сборка в EXE (Windows)
Используется **PyInstaller**:  
```powershell
pip install pyinstaller
pyinstaller run.py --name NeuroChat --windowed --onefile ^
  --add-data "theme/dark.qss;theme"
```
Готовый exe появится в `dist/`.

## 🤖 Автосборка через GitHub Actions
Если создать тег (например, `v1.0.0`) и отправить его на GitHub:  
```bash
git tag v1.0.0
git push origin v1.0.0
```
→ автоматически соберётся `NeuroChat.exe` и прикрепится к релизу.  

Файл workflow: `.github/workflows/release.yml`.

## 📜 Лицензия
Лицензия: **Non-Commercial Open License 1.0 (NCOL-1.0)**.  
Код можно использовать, изменять и распространять, но **запрещено коммерческое использование**.  
Текст лицензии смотри в [LICENSE](LICENSE).
