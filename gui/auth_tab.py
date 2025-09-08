from PyQt6 import QtWidgets
from app import db

class AuthTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Время", "Телефон", "Уровень", "Сообщение"])
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)

        row = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Обновить")
        row.addWidget(self.btn_refresh); row.addStretch(1)
        v.addLayout(row)

        self.btn_refresh.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self):
        logs = [r for r in db.list_logs(300) if r["source"] == "login"]
        self.table.setRowCount(len(logs))
        for i, r in enumerate(logs):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(r["ts"]))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(r["account_phone"] or ""))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(r["level"]))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(r["payload"]))
