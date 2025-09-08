
from PyQt6 import QtWidgets, QtCore
from app import db

class HumanTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.chk_auto = QtWidgets.QCheckBox("Авто‑тайминг (реалистичные случайные задержки)")
        layout.addWidget(self.chk_auto)

        auto_box = QtWidgets.QGroupBox("Диапазоны для авто‑тайминга")
        auto_form = QtWidgets.QFormLayout(auto_box)

        self.dbl_react_min = QtWidgets.QDoubleSpinBox(); self.dbl_react_min.setRange(0.0, 30.0); self.dbl_react_min.setSuffix(" сек")
        self.dbl_react_max = QtWidgets.QDoubleSpinBox(); self.dbl_react_max.setRange(0.0, 30.0); self.dbl_react_max.setSuffix(" сек")

        self.dbl_cps_min = QtWidgets.QDoubleSpinBox(); self.dbl_cps_min.setRange(0.1, 20.0); self.dbl_cps_min.setSingleStep(0.1); self.dbl_cps_min.setSuffix(" симв/сек")
        self.dbl_cps_max = QtWidgets.QDoubleSpinBox(); self.dbl_cps_max.setRange(0.1, 20.0); self.dbl_cps_max.setSingleStep(0.1); self.dbl_cps_max.setSuffix(" симв/сек")

        self.int_par_min = QtWidgets.QSpinBox(); self.int_par_min.setRange(0, 2000); self.int_par_min.setSuffix(" мс")
        self.int_par_max = QtWidgets.QSpinBox(); self.int_par_max.setRange(0, 2000); self.int_par_max.setSuffix(" мс")

        self.int_before_min = QtWidgets.QSpinBox(); self.int_before_min.setRange(0, 5000); self.int_before_min.setSuffix(" мс")
        self.int_before_max = QtWidgets.QSpinBox(); self.int_before_max.setRange(0, 5000); self.int_before_max.setSuffix(" мс")

        auto_form.addRow("Пауза после прочтения (мин):", self.dbl_react_min)
        auto_form.addRow("Пауза после прочтения (макс):", self.dbl_react_max)
        auto_form.addRow("Скорость печати (мин):", self.dbl_cps_min)
        auto_form.addRow("Скорость печати (макс):", self.dbl_cps_max)
        auto_form.addRow("Пауза между абзацами (мин):", self.int_par_min)
        auto_form.addRow("Пауза между абзацами (макс):", self.int_par_max)
        auto_form.addRow("Пауза перед отправкой (мин):", self.int_before_min)
        auto_form.addRow("Пауза перед отправкой (макс):", self.int_before_max)

        self.int_jitter = QtWidgets.QSpinBox(); self.int_jitter.setRange(0, 90); self.int_jitter.setSuffix(" %")
        auto_form.addRow("Джиттер задержек:", self.int_jitter)

        layout.addWidget(auto_box)

        opts_box = QtWidgets.QGroupBox("Поведение мессенджера")
        form = QtWidgets.QFormLayout(opts_box)

        self.chk_typing = QtWidgets.QCheckBox("Держать «печатает…» до фактической отправки ответа")
        self.cmb_read_policy = QtWidgets.QComboBox()
        self.cmb_read_policy.addItems(["immediate", "on_typing", "before_send"])
        self.cmb_read_policy.setEditable(False)

        self.edt_quiet = QtWidgets.QLineEdit(); self.edt_quiet.setPlaceholderText("например: 23:00-08:00, 13:00-14:00")
        self.spn_per_min = QtWidgets.QSpinBox(); self.spn_per_min.setRange(0, 60); self.spn_per_min.setToolTip("Макс. ответов в минуту на аккаунт (0 = без лимита)")

        form.addRow(self.chk_typing)
        form.addRow("Когда отмечать «прочитано»:", self.cmb_read_policy)
        form.addRow("Тихие часы:", self.edt_quiet)
        form.addRow("Лимит ответов в минуту:", self.spn_per_min)

        layout.addWidget(opts_box)

        
        # --- Группа: задержка при присоединении к чатам ---
        grp_join = QtWidgets.QGroupBox("Задержка при присоединении к чатам")
        formj = QtWidgets.QFormLayout(grp_join)
        self.chk_join_delay = QtWidgets.QCheckBox("Включить задержку перед вступлением")
        self.spn_join_min = QtWidgets.QDoubleSpinBox()
        self.spn_join_max = QtWidgets.QDoubleSpinBox()
        for spn in (self.spn_join_min, self.spn_join_max):
            spn.setDecimals(1); spn.setRange(0.0, 600.0)
        self.spn_join_min.setSuffix(" c"); self.spn_join_max.setSuffix(" c")
        formj.addRow(self.chk_join_delay)
        formj.addRow("Минимум:", self.spn_join_min)
        formj.addRow("Максимум:", self.spn_join_max)
        layout.addWidget(grp_join)
        
        btns = QtWidgets.QHBoxLayout()

        self.btn_save = QtWidgets.QPushButton("Сохранить")
        self.btn_reset = QtWidgets.QPushButton("Сброс")
        btns.addStretch(1); btns.addWidget(self.btn_reset); btns.addWidget(self.btn_save)
        layout.addLayout(btns)
        layout.addStretch(1)

        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset_to_defaults)

        def _toggle():
            on = self.chk_auto.isChecked()
            for w in [self.dbl_react_min, self.dbl_react_max, self.dbl_cps_min, self.dbl_cps_max,
                      self.int_par_min, self.int_par_max, self.int_before_min, self.int_before_max]:
                w.setEnabled(on)
        self.chk_auto.toggled.connect(_toggle)
        self._toggle = _toggle

    def _load(self):
        g = lambda k,d: db.get_setting(k, d) or d

        self.chk_auto.setChecked((g("human_auto_enabled", "1") == "1"))
        self.dbl_react_min.setValue(float(g("human_react_min_sec","3.0")))
        self.dbl_react_max.setValue(float(g("human_react_max_sec","4.0")))
        self.dbl_cps_min.setValue(float(g("human_typing_cps_min","3.2")))
        self.dbl_cps_max.setValue(float(g("human_typing_cps_max","6.8")))
        self.int_par_min.setValue(int(g("human_between_paragraph_min_ms","80")))
        self.int_par_max.setValue(int(g("human_between_paragraph_max_ms","200")))
        self.int_before_min.setValue(int(g("human_before_send_min_ms","120")))
        self.int_before_max.setValue(int(g("human_before_send_max_ms","400")))
        # join delay
        try:
            self.chk_join_delay.setChecked((g("join_delay_enabled","1")=="1"))
            self.spn_join_min.setValue(float(g("join_delay_min_sec","2.0")))
            self.spn_join_max.setValue(float(g("join_delay_max_sec","5.0")))
        except Exception:
            self.chk_join_delay.setChecked(True)
            self.spn_join_min.setValue(2.0)
            self.spn_join_max.setValue(5.0)

        self.int_jitter.setValue(int(g("human_jitter_pct","12")))

        self.chk_typing.setChecked((g("human_keep_typing_until_send","1") == "1"))
        rp = g("human_mark_read_policy","on_typing")
        i = max(0, self.cmb_read_policy.findText(rp)); self.cmb_read_policy.setCurrentIndex(i)
        self.edt_quiet.setText(g("human_quiet_hours",""))
        self.spn_per_min.setValue(int(g("human_limit_per_minute","0")))

        self._toggle()

    def _save(self):
        s = lambda k,v: db.set_setting(k, str(v))

        s("human_auto_enabled", "1" if self.chk_auto.isChecked() else "0")
        s("human_react_min_sec", self.dbl_react_min.value())
        s("human_react_max_sec", self.dbl_react_max.value())
        s("human_typing_cps_min", self.dbl_cps_min.value())
        s("human_typing_cps_max", self.dbl_cps_max.value())
        s("human_between_paragraph_min_ms", self.int_par_min.value())
        s("human_between_paragraph_max_ms", self.int_par_max.value())
        s("human_before_send_min_ms", self.int_before_min.value())
        s("human_before_send_max_ms", self.int_before_max.value())
        s("human_jitter_pct", self.int_jitter.value())

        s("human_keep_typing_until_send", "1" if self.chk_typing.isChecked() else "0")
        s("human_mark_read_policy", self.cmb_read_policy.currentText())
        s("human_quiet_hours", self.edt_quiet.text().strip())
        s("human_limit_per_minute", self.spn_per_min.value())
        s("join_delay_enabled", "1" if self.chk_join_delay.isChecked() else "0")
        s("join_delay_min_sec", self.spn_join_min.value())
        s("join_delay_max_sec", self.spn_join_max.value())
        QtWidgets.QMessageBox.information(self, "Готово", "Настройки сохранены.")

    def _reset_to_defaults(self):
        self.chk_auto.setChecked(True)
        self.dbl_react_min.setValue(3.0); self.dbl_react_max.setValue(4.0)
        self.dbl_cps_min.setValue(3.2); self.dbl_cps_max.setValue(6.8)
        self.int_par_min.setValue(80); self.int_par_max.setValue(200)
        self.int_before_min.setValue(120); self.int_before_max.setValue(400)
        self.int_jitter.setValue(12)
        self.chk_typing.setChecked(True)
        self.cmb_read_policy.setCurrentText("on_typing")
        self.edt_quiet.setText("")
        self.spn_per_min.setValue(0)
        QtWidgets.QMessageBox.information(self, "Сброс", "Значения по умолчанию восстановлены (не забудь «Сохранить»).")