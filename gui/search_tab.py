
from PyQt6 import QtWidgets, QtCore
import asyncio
from app.accounts import ACCOUNTS
from app.chats import search_public_chats_plus
from app import db

class SearchTab(QtWidgets.QWidget):
    add_to_mass_list = QtCore.pyqtSignal(list)
    def __init__(self):
        super().__init__()
        self.setLayout(QtWidgets.QVBoxLayout())
        row = QtWidgets.QHBoxLayout()
        self.account_select = QtWidgets.QComboBox()
        self.btn_acc_refresh = QtWidgets.QPushButton("Обновить аккаунты")
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Ключевые слова")
        self.limit_spin = QtWidgets.QSpinBox()
        self.limit_spin.setRange(10, 200)
        self.limit_spin.setValue(50)
        self.btn_search = QtWidgets.QPushButton("Найти")
        row.addWidget(QtWidgets.QLabel("Аккаунт:"))
        row.addWidget(self.account_select, 2)
        row.addWidget(self.btn_acc_refresh)
        row.addWidget(self.query, 4)
        row.addWidget(self.limit_spin)
        row.addWidget(self.btn_search)
        self.layout().addLayout(row)


        self.results = QtWidgets.QListWidget()
        self.layout().addWidget(self.results, 1)

        self.btn_add = QtWidgets.QPushButton("Добавить в список (массовое присоединение)")
        self.layout().addWidget(self.btn_add)

        self.btn_acc_refresh.clicked.connect(self.refresh_accounts_combo)
        self.btn_search.clicked.connect(self.do_search)
        self.btn_add.clicked.connect(self.add_selected_to_queue)

        self.refresh_accounts_combo()

    def refresh_accounts_combo(self):
        cur = self.account_select.currentText()
        self.account_select.clear()
        for a in ACCOUNTS.status():
            if a.get("running"):
                self.account_select.addItem(a["phone"])
        if cur:
            idx = self.account_select.findText(cur)
            if idx >= 0:
                self.account_select.setCurrentIndex(idx)

    def _get_worker(self):
        phone = self.account_select.currentText()
        if not phone:
            QtWidgets.QMessageBox.warning(self, "Аккаунт", "Нет активных аккаунтов.")
            return None, None
        w = ACCOUNTS.workers.get(phone)
        if not w or not w.running:
            QtWidgets.QMessageBox.warning(self, "Неактивно", "Аккаунт должен быть включён (вкладка «Запуск»).")
            return None, None
        return phone, w

    def do_search(self):
        phone, w = self._get_worker()
        if not w: return
        q = self.query.text().strip()
        if not q: return
        fut = asyncio.run_coroutine_threadsafe(search_public_chats_plus(w.client, q, per_query_limit=int(self.limit_spin.value())), w.loop)
        try:
            chats = fut.result(timeout=60)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Поиск не удался: {e}")
            return
        self.results.clear()
        self._items = []
        for c in chats:
            title = getattr(c, "title", "") or getattr(c, "username", "") or str(c.id)
            uname = getattr(c, "username", "") or ""
            item = QtWidgets.QListWidgetItem(f"{title} (@{uname}) id={c.id}")
            self.results.addItem(item)
            self._items.append({"title": title, "username": uname})

    def add_selected_to_queue(self):
        rows = [i.row() for i in self.results.selectedIndexes()]
        if not rows:
            QtWidgets.QMessageBox.information(self, "Выбор", "Выберите результаты поиска.")
            return
        count = 0
        for r in rows:
            rec = self._items[r]
            uname = rec["username"]
            if not uname:
                continue
            self.add_to_mass_list.emit(["@" + uname])
            count += 1
        QtWidgets.QMessageBox.information(self, "OK", f"Добавлено: {count}")