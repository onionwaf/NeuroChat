import sys, os, logging, argparse
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.join(os.path.dirname(__file__), "gui"))

from pathlib import Path
from app import db
from gui.main_window import run_app

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    try:
        if db.get_setting("debug_enabled","0") == "1":
            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger("telethon").setLevel(logging.DEBUG)
            logging.info("Debug mode enabled from settings.")
    except Exception as e:
        logging.getLogger().warning("Couldn't read debug setting yet: %s", e)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-db", action="store_true", help="Удалить БД data/neurobot.db и стартовать с нуля")
    args = parser.parse_args()

    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "neurobot.db"
    if args.reset_db and db_file.exists():
        try:
            db_file.unlink()
            print("База данных удалена:", db_file)
        except Exception as e:
            print("Не удалось удалить БД:", e)

    try:
        if hasattr(db, "init_db"):
            db.init_db()
        elif hasattr(db, "create_schema"):
            db.create_schema()
            if hasattr(db, "migrate_schema"):
                db.migrate_schema()
        else:
            db.init_db()
        if hasattr(db, "migrate_schema"):
            db.migrate_schema()
        logging.info("DB schema ready at %s", db_file)
    except Exception as e:
        logging.error("DB init failed: %s", e)

    setup_logging()

    logging.info("Starting GUI...")
    run_app()

if __name__ == "__main__":
    main()
