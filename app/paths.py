from pathlib import Path
import sys

def app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def data_dir() -> Path:
    p = app_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p

def sessions_dir() -> Path:
    p = data_dir() / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p

def db_path() -> Path:
    return data_dir() / "neurobot.db"

def resource_root() -> Path:
    # PyInstaller onefile extracts to _MEIPASS
    base = Path(getattr(sys, "_MEIPASS", app_root()))
    return base

def theme_file(name: str) -> Path:
    return resource_root() / "theme" / name
