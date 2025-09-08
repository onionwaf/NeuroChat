from PyQt6 import QtWidgets, QtCore
from app import db

def _human_bits():
    try:
        auto = db.get_setting("human_auto_enabled","0") == "1"
        typing = db.get_setting("human_keep_typing_until_send","0") == "1"
        rp = db.get_setting("human_mark_read_policy","on_typing")
        enabled = auto or typing
        return enabled, auto, typing, rp
    except Exception:
        return False, False, False, "unknown"

def _human_status_line():
    enabled, auto, typing, rp = _human_bits()
    return f"Человечность: {'включена' if enabled else 'выкл'}; авто‑тайминг: {'вкл' if auto else 'выкл'}; прочитано: {rp}."

def _has_accounts():
    try:
        cur = db.get_conn().execute("SELECT COUNT(*) FROM accounts")
        return (cur.fetchone() or (0,))[0] > 0
    except Exception:
        return False

def _api_ok():
    try:
        key = (db.get_setting("mistral_api_key","") or "").strip()
        mdl = (db.get_setting("mistral_model","") or "").strip()
        return bool(key) and bool(mdl)
    except Exception:
        return False

def _chats_ok():
    try:
        conn = db.get_conn()
        rows = conn.execute("SELECT account_phone, chat_id FROM chats WHERE active=1").fetchall()
        gt = (db.get_setting("global_triggers","") or "").strip()
        if gt and rows:
            return True
        for ap, cid in rows or []:
            cnt = conn.execute("SELECT COUNT(*) FROM triggers WHERE account_phone=? AND chat_id=?", (ap, cid)).fetchone()
            if (cnt or (0,))[0] > 0:
                return True
        return False
    except Exception:
        return False

class OnboardingDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Онбординг NeuroChattingBot")
        self.setModal(True)
        self.resize(620, 280)
        v = QtWidgets.QVBoxLayout(self)

        self.list = QtWidgets.QListWidget(); self.list.setUniformItemSizes(True)
        v.addWidget(self.list, 1)

        btn = QtWidgets.QPushButton("OK"); btn.clicked.connect(self.accept)
        row = QtWidgets.QHBoxLayout(); row.addStretch(1); row.addWidget(btn); v.addLayout(row)

        self.refresh()

    def _add(self, ok: bool, text: str):
        icon = "✅" if ok else "❌"
        self.list.addItem(QtWidgets.QListWidgetItem(f"{icon} {text}"))

    def refresh(self):
        self.list.clear()
        self._add(_has_accounts(), "Аккаунты: добавлены сессии")
        self._add(_api_ok(), "АИ‑мистрал: указан API‑ключ и выбрана модель")
        self._add(_chats_ok(), "Чаты: есть активные чаты и настроены триггеры (локальные или глобальные)")
        enabled, *_ = _human_bits()
        self._add(enabled, _human_status_line())
        self._add(True, "Запуск: после настройки вкладок запустите выбранные аккаунты")


def maybe_show_onboarding(parent=None):
    try:
        shown = db.get_setting("onboarding_shown","0") == "1"
    except Exception:
        shown = False
    if not shown:
        dlg = OnboardingDialog(parent); dlg.exec()
        try: db.set_setting("onboarding_shown","1")
        except Exception: pass
