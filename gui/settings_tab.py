from PyQt6 import QtWidgets
from app import db

def _normalize_phone(p: str) -> str:
    p = (p or '').strip()
    return p if p.startswith('+') or p == '' else '+' + p


class SettingsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)

        # --- Общие настройки ---
        g = QtWidgets.QGroupBox("Общие настройки")
        form = QtWidgets.QFormLayout(g)
        self.min_words = QtWidgets.QSpinBox(); self.min_words.setRange(0, 50); self.min_words.setValue(int(db.get_setting("min_words","3")))
        self.lang_ru = QtWidgets.QCheckBox("Русский"); self.lang_ru.setChecked(db.get_setting("lang_ru_enabled","1") == "1")
        self.lang_en = QtWidgets.QCheckBox("English"); self.lang_en.setChecked(db.get_setting("lang_en_enabled","1") == "1")
        self.anti_spam = QtWidgets.QCheckBox("Анти-спам (уникальные ответы)"); self.anti_spam.setChecked(db.get_setting("anti_spam_enabled","1") == "1")
        self.timeout = QtWidgets.QSpinBox(); self.timeout.setRange(5, 3600); self.timeout.setValue(int(db.get_setting("timeout_sec_per_chat","60")))
        self.logging = QtWidgets.QCheckBox("Вести логи"); self.logging.setChecked(db.get_setting("logging_enabled","1") == "1")
        self.global_triggers = QtWidgets.QPlainTextEdit(); self.global_triggers.setPlainText(db.get_setting("global_triggers",""))
        self.autostart = QtWidgets.QCheckBox("Автозапуск аккаунтов"); self.autostart.setChecked(db.get_setting("autostart_accounts","0") == "1")
        self.debug = QtWidgets.QCheckBox("Debug-режим"); self.debug.setChecked(db.get_setting("debug_enabled","0") == "1")
        form.addRow("Мин. слов:", self.min_words)
        langs = QtWidgets.QHBoxLayout(); langs.addWidget(self.lang_ru); langs.addWidget(self.lang_en); langs.addStretch(1)
        lh = QtWidgets.QWidget(); lh.setLayout(langs); form.addRow("Языки:", lh)
        form.addRow("", self.anti_spam)
        form.addRow("Таймаут (сек/чат):", self.timeout)
        form.addRow("", self.logging); form.addRow("", self.autostart); form.addRow("", self.debug)
        form.addRow("Глобальные триггеры:", self.global_triggers)
        btn = QtWidgets.QPushButton("Сохранить"); btn.clicked.connect(self.save)
        form.addRow(btn)
        v.addWidget(g)

        v.addWidget(SafetyPanel())
        v.addWidget(ProxyPanel())
        v.addStretch(1)

    def save(self):
        db.set_setting("min_words", str(self.min_words.value()))
        db.set_setting("lang_ru_enabled", "1" if self.lang_ru.isChecked() else "0")
        db.set_setting("lang_en_enabled", "1" if self.lang_en.isChecked() else "0")
        db.set_setting("anti_spam_enabled", "1" if self.anti_spam.isChecked() else "0")
        db.set_setting("timeout_sec_per_chat", str(self.timeout.value()))
        db.set_setting("logging_enabled", "1" if self.logging.isChecked() else "0")
        db.set_setting("global_triggers", (self.global_triggers.toPlainText() or '').replace('\n',','))
        db.set_setting("autostart_accounts", "1" if self.autostart.isChecked() else "0")
        db.set_setting("debug_enabled", "1" if self.debug.isChecked() else "0")
        QtWidgets.QMessageBox.information(self, "OK", "Сохранено.")

class SafetyPanel(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__("Параметры безопасности аккаунта")
        v = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Аккаунт:"))
        self.account_select = QtWidgets.QComboBox()
        self.btn_refresh = QtWidgets.QPushButton("Обновить")
        top.addWidget(self.account_select); top.addWidget(self.btn_refresh); top.addStretch(1)
        v.addLayout(top)
        form = QtWidgets.QFormLayout()
        self.safe_mode = QtWidgets.QCheckBox("Safe Mode (только слушать, без ответов)")
        self.min_gap = QtWidgets.QSpinBox(); self.min_gap.setRange(0, 3600000); self.min_gap.setSingleStep(1000)
        self.per_chat_gap = QtWidgets.QSpinBox(); self.per_chat_gap.setRange(0, 3600000); self.per_chat_gap.setSingleStep(1000)
        self.per_hour = QtWidgets.QSpinBox(); self.per_hour.setRange(0, 200)
        self.jitter = QtWidgets.QSpinBox(); self.jitter.setRange(0, 60000)
        self.pause_flood = QtWidgets.QSpinBox(); self.pause_flood.setRange(0, 120)
        form.addRow(self.safe_mode)
        form.addRow("Мин. интервал (мс):", self.min_gap)
        form.addRow("Мин. на чат (мс):", self.per_chat_gap)
        form.addRow("Ответов в час:", self.per_hour)
        form.addRow("Джиттер (мс):", self.jitter)
        form.addRow("Пауза при FloodWait (мин):", self.pause_flood)
        v.addLayout(form)
        self.btn_save = QtWidgets.QPushButton("Сохранить"); v.addWidget(self.btn_save)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_save.clicked.connect(self.save)
        self.refresh()

    def refresh(self):
        cur = self.account_select.currentText() if self.account_select.count()>0 else ""
        self.account_select.clear()
        for a in db.list_accounts():
            self.account_select.addItem(a['phone'])
        if cur:
            idx = self.account_select.findText(cur)
            if idx>=0: self.account_select.setCurrentIndex(idx)
        self._load()

    def _load(self):
        phone = self.account_select.currentText().strip() if self.account_select.count()>0 else ""
        lim = db.get_account_limits(phone) if phone else {}
        self.safe_mode.setChecked(bool(lim.get('safe_mode',1)))
        self.min_gap.setValue(int(lim.get('min_gap_ms',60000)))
        self.per_chat_gap.setValue(int(lim.get('per_chat_min_gap_ms',180000)))
        self.per_hour.setValue(int(lim.get('replies_per_hour',8)))
        self.jitter.setValue(int(lim.get('jitter_ms',8000)))
        self.pause_flood.setValue(int(lim.get('pause_on_flood_wait_min',45)))

    def save(self):
        phone = self.account_select.currentText().strip()
        if not phone: return
        db.set_account_limits(phone,
            safe_mode=1 if self.safe_mode.isChecked() else 0,
            min_gap_ms=int(self.min_gap.value()),
            per_chat_min_gap_ms=int(self.per_chat_gap.value()),
            replies_per_hour=int(self.per_hour.value()),
            jitter_ms=int(self.jitter.value()),
            pause_on_flood_wait_min=int(self.pause_flood.value()))
        QtWidgets.QMessageBox.information(self, "OK", "Сохранено.")



class ProxyPanel(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__("Прокси аккаунта")
        v = QtWidgets.QVBoxLayout(self)

        # header
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Аккаунт:"))
        self.account_select = QtWidgets.QComboBox()
        self.btn_refresh = QtWidgets.QPushButton("Обновить")
        top.addWidget(self.account_select); top.addWidget(self.btn_refresh); top.addStretch(1)
        v.addLayout(top)

        # form
        form = QtWidgets.QFormLayout()
        self.enabled = QtWidgets.QCheckBox("Использовать прокси")
        self.type = QtWidgets.QComboBox(); self.type.addItems(["SOCKS5","HTTP"])
        self.host = QtWidgets.QLineEdit()
        self.port = QtWidgets.QSpinBox(); self.port.setRange(1,65535)
        self.username = QtWidgets.QLineEdit()
        self.password = QtWidgets.QLineEdit(); self.password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        form.addRow(self.enabled)
        form.addRow("Тип:", self.type)
        form.addRow("Хост:", self.host)
        form.addRow("Порт:", self.port)
        form.addRow("Логин:", self.username)
        form.addRow("Пароль:", self.password)
        v.addLayout(form)

        btn = QtWidgets.QPushButton("Сохранить прокси")
        btn.clicked.connect(self.save)
        v.addWidget(btn)

        self.btn_refresh.clicked.connect(self.refresh_accounts)
        self.refresh_accounts()
        self.account_select.currentIndexChanged.connect(self.load_for_selected)
        self.load_for_selected()

    def refresh_accounts(self):
        self.account_select.clear()
        try:
            rows = db.list_accounts() if hasattr(db, "list_accounts") else []
            for r in rows:
                try:
                    phone = r["phone"]
                except Exception:
                    phone = (r.get("phone") if isinstance(r, dict) else r[0])
                self.account_select.addItem(_normalize_phone(str(phone)))
        except Exception:
            pass

    def load_for_selected(self):
        phone = self.account_select.currentText().strip()
        if not phone:
            return
        px = db.get_account_proxy(phone) if hasattr(db, "get_account_proxy") else {}
        self.enabled.setChecked(bool(int(px.get("enabled",0) or 0)))
        self.type.setCurrentText((px.get("type","SOCKS5") or "SOCKS5").upper())
        self.host.setText(px.get("host","") or "")
        try:
            self.port.setValue(int(px.get("port",0) or 0))
        except Exception:
            self.port.setValue(0)
        self.username.setText(px.get("username","") or "")
        self.password.setText(px.get("password","") or "")

    def save(self):
        phone = _normalize_phone(self.account_select.currentText().strip())
        if not phone:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Нет выбранного аккаунта.")
            return
        if self.enabled.isChecked():
            if not self.host.text().strip() or int(self.port.value() or 0) == 0:
                QtWidgets.QMessageBox.warning(self, "Ошибка", "Укажите хост и порт для прокси, или снимите галочку.")
                return
        try:
            db.set_account_proxy(
                phone,
                1 if self.enabled.isChecked() else 0,
                self.type.currentText().upper(),
                self.host.text().strip(),
                int(self.port.value() or 0),
                self.username.text().strip() or None,
                self.password.text().strip() or None,
            )
            px = db.get_account_proxy(phone)
            try:
                db.log("INFO", "proxy", f"Saved proxy for {phone}: enabled={px.get('enabled')} host={px.get('host')} port={px.get('port')}", phone)
            except Exception:
                pass
            QtWidgets.QMessageBox.information(self, "OK", f"Прокси сохранён.\nenabled={px.get('enabled')} type={px.get('type')}\nhost={px.get('host')} port={px.get('port')}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить прокси: {e}")
