import logging
from PyQt6 import QtWidgets
import sys
from pathlib import Path
from app.paths import theme_file
import logging
from app import db
from .accounts_tab import AccountsTab
from .chats_tab import ChatsTab
from .ai_tab import AITab
from .search_tab import SearchTab
from .settings_tab import SettingsTab
from .logs_tab import LogsTab
from .help_tab import HelpTab
from .runner_tab import RunnerTab
from .human_tab import HumanTab
from .onboarding import maybe_show_onboarding

def run_app():
    db.init_db()
    app = QtWidgets.QApplication(sys.argv)
    # Ensure graceful shutdown of Telethon workers on app exit
    try:
        from app.accounts import ACCOUNTS
        app.aboutToQuit.connect(lambda: ACCOUNTS.stop_all_and_join())
    except Exception:
        pass
    # Apply dark theme (QSS)
    try:
        qss_path = theme_file("dark.qss")
        if qss_path.exists():
            app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
            logging.info("Dark theme loaded: %s", qss_path)
        else:
            logging.warning("Dark theme not found: %s", qss_path)
    except Exception as e:
        logging.warning("Theme not applied: %s", e)
    w = QtWidgets.QMainWindow()
    w.setWindowTitle("NeuroChattingBot")
    
    tabs = QtWidgets.QTabWidget()
    accounts_tab = AccountsTab(); chats_tab = ChatsTab(); search_tab = SearchTab()
    tabs.addTab(accounts_tab, "Аккаунты")
    tabs.addTab(chats_tab, "Чаты")
    tabs.addTab(search_tab, "Поиск")
    tabs.addTab(AITab(), "АИ-мистрал")
    tabs.addTab(SettingsTab(), "Настройки")
    tabs.addTab(HumanTab(), "Человечность")
    tabs.addTab(RunnerTab(), "Запуск")
    tabs.addTab(LogsTab(), "Логи")
    tabs.addTab(HelpTab(), "Справка")

    # Wire Search → Chats (add results to mass list)
    try:
        search_tab.add_to_mass_list.connect(chats_tab.on_add_from_search)
    except Exception:
        pass
    w.setCentralWidget(tabs)

    w.resize(1200, 760)
    w.show()
    maybe_show_onboarding(w)
    sys.exit(app.exec())
