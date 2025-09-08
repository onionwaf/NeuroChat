# NeuroChat

Desktop AI chat client with a PyQt6 GUI. Integrates Mistral API and optional Telegram via Telethon.

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
Environment variables are loaded from `.env` (via `python-dotenv`). Do **NOT** commit real secrets.
See `.env.example` for the list of supported variables.

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
- Add any extra resource folders with additional `--add-data` entries.
- If dynamic imports are missed, use a `.spec` (see `neurochat.spec`).

## CI: GitHub Actions Release
On tag push like `v1.0.0`, CI builds the Windows exe and attaches it to the GitHub Release.
Workflow file: `.github/workflows/release.yml`.

## License
This repository uses **Non‑Commercial Open License 1.0 (NCOL‑1.0)** — you can use, modify, and distribute the source,
but **commercial use is not permitted**. See [LICENSE](LICENSE) for full text.
If you prefer a permissive OSI license, consider MIT/Apache‑2.0 instead.
