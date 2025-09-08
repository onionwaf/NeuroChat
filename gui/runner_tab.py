from PyQt6 import QtWidgets, QtCore
from app.accounts import ACCOUNTS
from .credentials_dialog import CredentialsDialog
from app import db


class _JoinWorker(QtCore.QThread):
    finishedWithCount = QtCore.pyqtSignal(int)
    def run(self):
        try:
            n = ACCOUNTS.process_join_queue_once()
            if n is None:
                n = 0
        except Exception:
            n = 0
        self.finishedWithCount.emit(int(n))

class RunnerTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)

        row = QtWidgets.QHBoxLayout()
        self.btn_start_all = QtWidgets.QPushButton("Запустить все")
        self.btn_stop_all = QtWidgets.QPushButton("Остановить все")
        self.btn_refresh = QtWidgets.QPushButton("Обновить")
        self.btn_process_join = QtWidgets.QPushButton("Обработать очередь сейчас")
        self._join_worker = None
        self.auto_timer_chk = QtWidgets.QCheckBox("Автообработка очереди каждые 30с")
        row.addWidget(self.btn_start_all); row.addWidget(self.btn_stop_all); row.addWidget(self.btn_refresh)
        row.addWidget(self.btn_process_join); row.addWidget(self.auto_timer_chk); row.addStretch(1)
        v.addLayout(row)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Телефон","Статус","Активных чатов","Ответов (сессия)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)

        self.btn_start_all.clicked.connect(self.start_all)
        self.btn_stop_all.clicked.connect(self.stop_all)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_process_join.clicked.connect(self.process_join)
        self.auto_timer_chk.stateChanged.connect(self.toggle_timer)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(30_000)
        self.timer.timeout.connect(self.process_join_if_needed)

        self.refresh()

    def start_all(self):
        # ensure global Telegram API id/hash once
        try:
            api_id = int(db.get_setting("telegram_api_id","0") or 0)
            api_hash = db.get_setting("telegram_api_hash","")
        except Exception:
            api_id, api_hash = 0, ""
        if not api_id or not api_hash:
            dlg = CredentialsDialog(self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                if not dlg.save():
                    return
            else:
                return
        for r in db.list_accounts():
            ACCOUNTS.start_account(r["phone"])
        if db.get_setting("auto_join_on_start","0") == "1":
            ACCOUNTS.process_join_queue_once()
        self.refresh()

    def stop_all(self):
        ACCOUNTS.stop_all()
        self.refresh()

    def refresh(self):
        st = ACCOUNTS.status()
        self.table.setRowCount(len(st))
        for i, r in enumerate(st):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(r["phone"]))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem("Запущен" if r["running"] else "Остановлен"))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(r["active_chats"])))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(r["messages_processed"])))

    def process_join(self):
        if self._join_worker and self._join_worker.isRunning():
            return
        self.btn_process_join.setEnabled(False)
        self._join_worker = _JoinWorker(self)
        self._join_worker.finishedWithCount.connect(self._on_join_done)
        self._join_worker.finished.connect(lambda: self.btn_process_join.setEnabled(True))
        self._join_worker.start()

    def _on_join_done(self, n: int):
        if n > 0:
            QtWidgets.QMessageBox.information(self, "Готово", f"Успешно присоединились: {n}")

    def  toggle_timer(self):
        if self.auto_timer_chk.isChecked():
            self.timer.start()
        else:
            self.timer.stop()

    def process_join_if_needed(self):
        if self._join_worker and self._join_worker.isRunning():
            return
        self.process_join()
