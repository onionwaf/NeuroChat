from PyQt6 import QtWidgets, QtCore
from app import db

class LogsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)

        # Controls
        controls = QtWidgets.QHBoxLayout()
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.source_edit = QtWidgets.QLineEdit()
        self.source_edit.setPlaceholderText("Источник (опц.)")
        self.autoscroll_chk = QtWidgets.QCheckBox("Автопрокрутка")
        self.autoscroll_chk.setChecked(True)
        self.autorefresh_chk = QtWidgets.QCheckBox("Автообновление")
        self.autorefresh_chk.setChecked(True)
        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" c")
        self.btn_refresh = QtWidgets.QPushButton("Обновить сейчас")
        self.btn_save = QtWidgets.QPushButton("Сохранить в CSV")

        controls.addWidget(QtWidgets.QLabel("Уровень:")); controls.addWidget(self.level_combo)
        controls.addWidget(QtWidgets.QLabel("Источник:")); controls.addWidget(self.source_edit)
        controls.addWidget(self.autoscroll_chk)
        controls.addWidget(self.autorefresh_chk)
        controls.addWidget(QtWidgets.QLabel("каждые")); controls.addWidget(self.interval_spin)
        controls.addWidget(self.btn_refresh); controls.addWidget(self.btn_save)
        controls.addStretch(1)
        v.addLayout(controls)

        # Table
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Время", "Уровень", "Источник", "Телефон", "Чат", "Сообщение"])
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)

        # Signals
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_save.clicked.connect(self.save_csv)
        self.level_combo.currentIndexChanged.connect(self.refresh)
        self.source_edit.returnPressed.connect(self.refresh)
        self.autorefresh_chk.toggled.connect(self._toggle_timer)
        self.interval_spin.valueChanged.connect(self._toggle_timer)

        # Timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._toggle_timer()

        # Initial
        self.refresh()

    def _toggle_timer(self):
        self.timer.stop()
        if self.autorefresh_chk.isChecked():
            self.timer.start(self.interval_spin.value() * 1000)

    def refresh(self):
        try:
            level = self.level_combo.currentText().strip() or None
            source = self.source_edit.text().strip() or None
            bar = self.table.verticalScrollBar()
            keep_pos = bar.value()
            rows = db.list_logs(200, level=level, source=source)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить логи: {e}")
            return

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(r.get("ts", ""))))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(r.get("level", ""))))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(r.get("source", ""))))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(r.get("account_phone", ""))))
            chat_disp = str(r.get("chat_id", ""))
            title = r.get("chat_title") or ""
            if title:
                chat_disp = f"{chat_disp} ({title})"
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(chat_disp))
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(r.get("payload", ""))))

        if self.autoscroll_chk.isChecked():
            self.table.verticalScrollBar().setValue(0)
        else:
            self.table.verticalScrollBar().setValue(keep_pos)

    def save_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Сохранить CSV", "neurobot_logs.csv", "CSV (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts", "level", "source", "phone", "chat", "payload"])
            for i in range(self.table.rowCount()):
                row = [
                    self.table.item(i, 0).text() if self.table.item(i,0) else "",
                    self.table.item(i, 1).text() if self.table.item(i,1) else "",
                    self.table.item(i, 2).text() if self.table.item(i,2) else "",
                    self.table.item(i, 3).text() if self.table.item(i,3) else "",
                    self.table.item(i, 4).text() if self.table.item(i,4) else "",
                    self.table.item(i, 5).text() if self.table.item(i,5) else "",
                ]
                w.writerow(row)
        QtWidgets.QMessageBox.information(self, "OK", "Сохранено.")
