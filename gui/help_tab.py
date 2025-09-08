
from PyQt6 import QtWidgets
from .onboarding import maybe_show_onboarding
from app import db

def _human_status():
    try:
        auto = db.get_setting("human_auto_enabled","0") == "1"
        typing = db.get_setting("human_keep_typing_until_send","0") == "1"
        rp = db.get_setting("human_mark_read_policy","on_typing")
        enabled = auto or typing
        return f"Человечность: {'включена' if enabled else 'выключена'}; авто‑тайминг: {'вкл' if auto else 'выкл'}; прочитано: {rp}."
    except Exception:
        return "Человечность: статус недоступен."

def _help_html():
    return f"""
<h2>NeuroChattingBot — справка</h2>
<p>Мульти‑аккаунтный Telegram‑бот. Слушает выбранные чаты и по триггерам отвечает через Mistral API.
Есть Safe Mode, лимиты, прокси и режим «Человечность».</p>

<p><b>{_human_status()}</b></p>

<h3>Быстрый старт</h3>
<ol>
<li><b>Аккаунты</b> → добавьте/импортируйте сессии.</li>
<li><b>АИ-мистрал</b> → укажите MISTRAL_API_KEY, модель и проверьте API.</li>
<li><b>Чаты</b> → загрузите диалоги, отметьте «Активен», задайте триггеры.</li>
<li><b>Настройки</b> → при необходимости включите Safe Mode/лимиты/прокси.</li>
<li><b>Человечность</b> → настройте реалистичные задержки и «печатает…».</li>
<li><b>Запуск</b> → запустите аккаунты.</li>
</ol>
"""

class HelpTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)

        row = QtWidgets.QHBoxLayout()
        self.btn_onboarding = QtWidgets.QPushButton("Показать онбординг")
        self.btn_refresh = QtWidgets.QPushButton("Обновить статус")
        row.addWidget(self.btn_onboarding); row.addWidget(self.btn_refresh); row.addStretch(1)
        v.addLayout(row)

        self.view = QtWidgets.QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setHtml(_help_html())
        v.addWidget(self.view, 1)

        self.btn_onboarding.clicked.connect(self._run_onboarding)
        self.btn_refresh.clicked.connect(self._refresh_status)

    def _refresh_status(self):
        self.view.setHtml(_help_html())

    def _run_onboarding(self):
        try:
            db.set_setting("onboarding_shown", "0")
        except Exception:
            pass
        maybe_show_onboarding(self)
        self._refresh_status()
