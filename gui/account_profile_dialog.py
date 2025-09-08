from PyQt6 import QtWidgets, QtCore
from app import db

class AccountProfileDialog(QtWidgets.QDialog):
    def __init__(self, phone: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Профиль аккаунта: {phone}")
        self.phone = phone
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.edt_prompt = QtWidgets.QPlainTextEdit(); self.edt_prompt.setMinimumHeight(120)
        self.edt_triggers = QtWidgets.QPlainTextEdit(); self.edt_triggers.setPlaceholderText("триггеры через запятую")

        self.chk_ru = QtWidgets.QCheckBox("Разрешить RU")
        self.chk_en = QtWidgets.QCheckBox("Разрешить EN")
        self.spn_min_words = QtWidgets.QSpinBox(); self.spn_min_words.setRange(0, 50)

        self.chk_antispam = QtWidgets.QCheckBox("Анти-спам (не отвечать на повторы)")
        self.spn_timeout = QtWidgets.QSpinBox(); self.spn_timeout.setRange(0, 3600); self.spn_timeout.setSuffix(" сек/чат");

        self.spn_jitter = QtWidgets.QSpinBox(); self.spn_jitter.setRange(0, 90); self.spn_jitter.setSuffix(" %")
        self.spn_think = QtWidgets.QSpinBox(); self.spn_think.setRange(0, 10000); self.spn_think.setSuffix(" мс")

        form.addRow("Системный промпт:", self.edt_prompt)
        form.addRow("Триггеры:", self.edt_triggers)
        form.addRow("Мин. слов:", self.spn_min_words)
        form.addRow(self.chk_ru, self.chk_en)
        form.addRow(self.chk_antispam)
        form.addRow("Таймаут между ответами:", self.spn_timeout)
        form.addRow("Джиттер задержек:", self.spn_jitter)
        form.addRow("Время подумать:", self.spn_think)

        layout.addLayout(form)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.btn_copy = QtWidgets.QPushButton("Скопировать из глобальных")
        self.btn_copy.clicked.connect(self._copy_globals)
        layout.addWidget(self.btn_copy)

    def _g(self, key, default=None):
        return db.get_acc_setting(self.phone, key, default)

    def _load(self):
        g = lambda k,d: self._g(k, db.get_setting(k, d))

        self.edt_prompt.setPlainText(g("prompt_system", ""))
        self.edt_triggers.setPlainText(g("triggers_csv", ""))

        self.spn_min_words.setValue(int(g("min_words", "3")))
        self.chk_ru.setChecked(g("lang_ru_enabled", db.get_setting("lang_ru_enabled","1")) == "1")
        self.chk_en.setChecked(g("lang_en_enabled", db.get_setting("lang_en_enabled","1")) == "1")
        self.chk_antispam.setChecked(g("anti_spam_enabled", db.get_setting("anti_spam_enabled","1")) == "1")
        self.spn_timeout.setValue(int(g("timeout_sec_per_chat", db.get_setting("timeout_sec_per_chat","60"))))

        self.spn_jitter.setValue(int(g("human_jitter_pct", db.get_setting("human_jitter_pct","12"))))
        self.spn_think.setValue(int(g("human_think_ms", db.get_setting("human_think_ms","600"))))

    def _save(self):
        s = lambda k,v: db.set_acc_setting(self.phone, k, str(v))
        s("prompt_system", self.edt_prompt.toPlainText())
        s("triggers_csv", self.edt_triggers.toPlainText())
        s("min_words", self.spn_min_words.value())
        s("lang_ru_enabled", "1" if self.chk_ru.isChecked() else "0")
        s("lang_en_enabled", "1" if self.chk_en.isChecked() else "0")
        s("anti_spam_enabled", "1" if self.chk_antispam.isChecked() else "0")
        s("timeout_sec_per_chat", self.spn_timeout.value())
        s("human_jitter_pct", self.spn_jitter.value())
        s("human_think_ms", self.spn_think.value())
        QtWidgets.QMessageBox.information(self, "Готово", "Профиль сохранён.")
        self.accept()

    def _copy_globals(self):
        keys = ["prompt_system","triggers_csv","min_words","lang_ru_enabled","lang_en_enabled","anti_spam_enabled","timeout_sec_per_chat","human_jitter_pct","human_think_ms"]
        for k in keys:
            db.set_acc_setting(self.phone, k, db.get_setting(k, db.get_setting(k, "")))
        QtWidgets.QMessageBox.information(self, "Готово", "Скопировано из глобальных. Не забудь нажать Сохранить.")
