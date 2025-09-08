
import logging
import re
from PyQt6 import QtWidgets, QtCore
import asyncio

from app import db
from app.accounts import ACCOUNTS
from app.chats import parse_chat_line
from app.triggers import split_triggers


def canonical_phone(s: str) -> str:
    s = (s or "").strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    return ("+" + digits) if digits else s

class ChatsTab(QtWidgets.QWidget):
    def current_account_phone(self) -> str:
        try:
            return canonical_phone(self.account_select.currentText())
        except Exception:
            return ""

    def __init__(self):
        super().__init__()
        root = QtWidgets.QVBoxLayout(self)

        # ---------- Массовое присоединение ----------
        gb = QtWidgets.QGroupBox("Массовое присоединение к чатам")
        gbl = QtWidgets.QVBoxLayout(gb)
        self.mass_edit = QtWidgets.QPlainTextEdit()
        self.mass_edit.setPlaceholderText("@username\nhttps://t.me/xxx\nhttps://t.me/+inviteHash\n...")
        rowm = QtWidgets.QHBoxLayout()
        self.btn_mass_save = QtWidgets.QPushButton("Сохранить список")
        self.btn_mass_clear = QtWidgets.QPushButton("Очистить")
        self.auto_join = QtWidgets.QCheckBox("Автоприсоединение при старте")
        self.auto_join.setChecked(db.get_setting("auto_join_on_start","0") == "1")
        self.btn_mass_run = QtWidgets.QPushButton("Присоединить сейчас")
        rowm.addWidget(self.btn_mass_save)
        rowm.addWidget(self.btn_mass_clear)
        rowm.addWidget(self.auto_join)
        rowm.addWidget(self.btn_mass_run)
        gbl.addWidget(self.mass_edit)
        gbl.addLayout(rowm)
        root.addWidget(gb)

        # Очередь присоединений
        self.queue_table = QtWidgets.QTableWidget(0,5)
        self.queue_table.setHorizontalHeaderLabels(["ID","Source","Username","Invite","Статус"])
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.queue_table)

        # Верхняя панель: загрузка диалогов + выбор аккаунта
        top = QtWidgets.QHBoxLayout()
        self.btn_load_dialogs = QtWidgets.QPushButton("Загрузить диалоги")
        top.addStretch(1)
        top.addWidget(self.btn_load_dialogs)
        top.addWidget(QtWidgets.QLabel("Аккаунт:"))
        self.account_select = QtWidgets.QComboBox()
        self.btn_acc_refresh = QtWidgets.QPushButton("Обновить аккаунты")
        top.addWidget(self.account_select, 1)
        top.addWidget(self.btn_acc_refresh)
        root.addLayout(top)
        self.account_select.currentIndexChanged.connect(self.refresh_table)

        # Таблица чатов и триггеры
        self.table = QtWidgets.QTableWidget(0,7)
        self.table.setHorizontalHeaderLabels(["Телефон","Chat ID","Название","Username","Активен","Последняя причина","Доступно до"])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

        row_act = QtWidgets.QHBoxLayout()
        self.btn_activate = QtWidgets.QPushButton("Активировать выбранные")
        self.btn_deactivate = QtWidgets.QPushButton("Деактивировать выбранные")
        row_act.addWidget(self.btn_activate)
        row_act.addWidget(self.btn_deactivate)
        root.addLayout(row_act)

        form = QtWidgets.QFormLayout()
        self.triggers_edit = QtWidgets.QLineEdit()
        self.btn_apply = QtWidgets.QPushButton("Сохранить триггеры")
        form.addRow("Триггеры (через запятую):", self.triggers_edit)
        self.btn_clear_trg = QtWidgets.QPushButton("Очистить триггеры (выбранные)")
        row_btns = QtWidgets.QHBoxLayout(); row_btns.addWidget(self.btn_apply); row_btns.addWidget(self.btn_clear_trg); form.addRow(row_btns)
        root.addLayout(form)

        # Сигналы
        self.btn_mass_save.clicked.connect(self.mass_save)
        self.btn_mass_clear.clicked.connect(lambda: self.mass_edit.setPlainText(""))
        self.auto_join.stateChanged.connect(self._save_auto_join)
        self.btn_mass_run.clicked.connect(self.mass_run)
        self.btn_load_dialogs.clicked.connect(self.load_dialogs)
        self.btn_acc_refresh.clicked.connect(self.refresh_accounts_combo)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.btn_activate.clicked.connect(self._activate_selected)
        self.btn_deactivate.clicked.connect(self._deactivate_selected)
        self.btn_apply.clicked.connect(self.apply_triggers)
        self.btn_clear_trg.clicked.connect(self.clear_triggers_selected)

        self.refresh_accounts_combo()
        self.refresh_queue()
        self.refresh_table()

    # ---------- Массовое присоединение ----------
    def _save_auto_join(self):
        db.set_setting("auto_join_on_start", "1" if self.auto_join.isChecked() else "0")

    def mass_save(self):
        lines = [l.strip() for l in self.mass_edit.toPlainText().splitlines() if l.strip()]
        for ln in lines:
            u, inv = parse_chat_line(ln)
            db.add_join_source(ln, u, inv)
        QtWidgets.QMessageBox.information(self, "OK", f"Добавлено в очередь: {len(lines)}")
        self.refresh_queue()

    def mass_run(self):
        n = ACCOUNTS.process_join_queue_once()
        QtWidgets.QMessageBox.information(self, "Результат", f"Успешно присоединились: {n}")
        self.refresh_queue()

    def refresh_queue(self):
        items = list(db.list_join_items(None, 500))
        self.queue_table.setRowCount(len(items))
        for i, r in enumerate(items):
            self.queue_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(r["id"])))
            self.queue_table.setItem(i, 1, QtWidgets.QTableWidgetItem(r["source"] or ""))
            self.queue_table.setItem(i, 2, QtWidgets.QTableWidgetItem(r["username"] or ""))
            self.queue_table.setItem(i, 3, QtWidgets.QTableWidgetItem(r["invite_hash"] or ""))
            self.queue_table.setItem(i, 4, QtWidgets.QTableWidgetItem(r["status"] or ""))

    def refresh_accounts_combo(self):
        self.account_select.blockSignals(True)
        self.account_select.clear()
        try:
            phones = [a['phone'] for a in db.list_accounts()]
        except Exception as e:
            logging.exception("refresh_accounts_combo failed: %s", e)
            phones = []
        for ph in phones:
            self.account_select.addItem(ph)
        if phones:
            self.account_select.setCurrentIndex(0)
        self.account_select.blockSignals(False)

    # ---------- Диалоги/чаты/триггеры ----------
    def _running_worker(self):
        # Используем только выбранный аккаунт. Без падения на «любой запущенный»,
        # чтобы исключить путаницу, когда грузятся диалоги другого номера.
        try:
            sel = self.account_select.currentText().strip()
        except Exception:
            sel = ""
        if not sel:
            QtWidgets.QMessageBox.warning(self, "Нет аккаунта", "Выберите аккаунт сверху.")
            return None, None
        w = ACCOUNTS.workers.get(sel)
        if not (w and getattr(w,'client',None) and getattr(w,'running',False)):
            QtWidgets.QMessageBox.warning(self, "Не запущен", "Аккаунт не запущен. Перейдите во вкладку «Запуск» и нажмите Старт для выбранного номера.")
            return None, None
        return sel, w

    def load_dialogs(self):
        phone, w = self._running_worker()
        if not w:
            return

        async def _load():
            from telethon.utils import get_peer_id
            dialogs = await w.client.get_dialogs(limit=500)
            for d in dialogs:
                entity = d.entity
                try:
                    cid = get_peer_id(entity)
                except Exception:
                    continue
                title = getattr(entity, "title", "") or getattr(entity, "username", "") or str(cid)
                uname = getattr(entity, "username", "") or ""
                db.upsert_chat(phone, cid, title, uname)

            # деактивировать всё кроме указанных в mass_edit
            allow = set()
            for ln in (self.mass_edit.toPlainText() or '').splitlines():
                ln = (ln or '').strip()
                if not ln:
                    continue
                if ln.startswith('https://t.me/'):
                    uname = ln.split('/')[-1].lstrip('+')
                elif ln.startswith('@'):
                    uname = ln[1:]
                else:
                    uname = ln
                allow.add(uname.lower())

            for r in db.list_chats(phone):
                uname = (r["chat_username"] or "").lower()
                db.set_chat_active(phone, r["chat_id"], uname in allow)

        fut = asyncio.run_coroutine_threadsafe(_load(), w.loop)
        try:
            fut.result(timeout=120)
            self.refresh_table()
            QtWidgets.QMessageBox.information(self, "Готово", "Диалоги загружены.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить диалоги: {e}")

        # After refresh, select first row (if any) so user sees triggers immediately
        try:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
        except Exception:
            pass
        # Update triggers field for current selection
        try:
            self._on_selection_changed()
        except Exception:
            pass
    def _on_cell_changed(self, row, col):
        if col != 4:
            return
        try:
            phone = self.table.item(row, 0).text()
            chat_id = int(self.table.item(row, 1).text())
            active = self.table.item(row, 4).checkState() == QtCore.Qt.CheckState.Checked
            db.set_chat_active(phone, chat_id, active)
        except Exception:
            pass


    def _selected_rows(self):
        sel = sorted({ix.row() for ix in self.table.selectionModel().selectedIndexes()})
        return sel

    def _activate_selected(self):
        for r in self._selected_rows():
            phone = self.table.item(r,0).text()
            chat_id = int(self.table.item(r,1).text())
            db.set_chat_active(phone, chat_id, True)
        self.refresh_table()

    def _deactivate_selected(self):
        for r in self._selected_rows():
            phone = self.table.item(r,0).text()
            chat_id = int(self.table.item(r,1).text())
            db.set_chat_active(phone, chat_id, False)
        self.refresh_table()

    def apply_triggers(self):
        # Применить ко всем выделенным чатам
        text = (self.triggers_edit.text() or "").strip()
        phrases = split_triggers(text)
        rows = self._selected_rows()
        if not rows:
            QtWidgets.QMessageBox.information(self, "Нет выбора", "Выделите хотя бы один чат в таблице.")
            return
        for r in rows:
            phone = canonical_phone(self.table.item(r,0).text())
            chat_id = int(self.table.item(r,1).text())
            try:
                for old in db.list_triggers(phone, chat_id):
                    db.delete_trigger(phone, chat_id, old)
            except Exception:
                pass
            for t in phrases:
                db.add_trigger(phone, chat_id, t)
        QtWidgets.QMessageBox.information(self, "OK", "Триггеры сохранены.")
        try:
            self._on_selection_changed()
        except Exception:
            pass


    def append_to_mass_list(self, items: list[str]):
        cur = self.mass_edit.toPlainText().strip()
        lines = [cur] if cur else []
        for it in items or []:
            t = (it or '').strip()
            if not t:
                continue
            if not (t.startswith('@') or t.startswith('http')):
                t = '@' + t
            lines.append(t)
        self.mass_edit.setPlainText('\n'.join(lines))


    def _on_selection_changed(self):
        """
        When user selects a single chat row, load its triggers from DB and show in the edit.
        """
        rows = self._selected_rows()
        if len(rows) != 1:
            self.triggers_edit.setText("")
            return
        r = rows[0]
        try:
            phone = canonical_phone(self.table.item(r, 0).text()) or self.current_account_phone()
            chat_id = int(self.table.item(r, 1).text())
        except Exception:
            self.triggers_edit.setText("")
            return
        try:
            phrases = db.list_triggers(phone, chat_id) or []
        except Exception:
            phrases = []
        self.triggers_edit.setText(", ".join(phrases))


    def refresh_table(self):
        """Reload chats for the selected account and update triggers field."""
        try:
            phone = self.account_select.currentText().strip() if self.account_select.count() > 0 else None
        except Exception:
            phone = None
        try:
            rows = list(db.list_chats(phone)) if phone else []
        except Exception:
            rows = []

        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            try:
                rr = dict(r)
            except Exception:
                rr = None
            def getv(key):
                if rr is not None:
                    return rr.get(key)
                try:
                    return r[key]
                except Exception:
                    return None
            ap = getv("account_phone")
            cid = getv("chat_id")
            title = getv("chat_title") or ""
            uname = getv("chat_username") or ""
            active = getv("active")
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(ap if ap is not None else "")))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(cid if cid is not None else "")))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(title))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(uname))
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(chk.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            chk.setCheckState(QtCore.Qt.CheckState.Checked if active else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(i, 4, chk)
            try:
                diag = db.get_chat_diag(ap, cid)
                reason = diag.get("last_skip_reason") or diag.get("last_action") or ""
                next_ts = diag.get("next_eligible_ts") or ""
            except Exception:
                reason, next_ts = "", ""
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(reason)))
            self.table.setItem(i, 6, QtWidgets.QTableWidgetItem(str(next_ts)))
        self.table.blockSignals(False)

        try:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
        except Exception:
            pass
        try:
            self._on_selection_changed()
        except Exception:
            pass



    def clear_triggers_selected(self):
        rows = self._selected_rows()
        if not rows:
            QtWidgets.QMessageBox.information(self, "Нет выбора", "Выделите хотя бы один чат.")
            return
        for r in rows:
            try:
                phone = canonical_phone(self.table.item(r,0).text())
                chat_id = int(self.table.item(r,1).text())
                for old in db.list_triggers(phone, chat_id):
                    db.delete_trigger(phone, chat_id, old)
            except Exception:
                continue
        QtWidgets.QMessageBox.information(self, "OK", "Триггеры очищены.")
        try:
            self._on_selection_changed()
        except Exception:
            pass


    # ---- External hook from SearchTab ----
    def on_add_from_search(self, items: list):
        from app.chats import parse_chat_line
        from app import db
        current = self.mass_edit.toPlainText().strip()
        add_text = "\n".join(items)
        self.mass_edit.setPlainText((current + "\n" + add_text).strip() if current else add_text)
        for s in items:
            u, inv = parse_chat_line(s)
            db.add_join_source(s, u, inv)
        self.refresh_queue()
