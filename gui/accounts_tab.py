
def _socks5_handshake(sock, username=None, password=None, timeout=5.0):
    sock.settimeout(timeout)
    # Greeting
    methods = [0x00] if not username else [0x00, 0x02]
    sock.sendall(bytes([5, len(methods), *methods]))
    resp = sock.recv(2)
    if len(resp) < 2 or resp[0] != 5 or resp[1] == 0xFF:
        raise RuntimeError("SOCKS5: no acceptable auth methods")
    if resp[1] == 0x02:
        if username is None:
            raise RuntimeError("SOCKS5: server requires username/password")
        u = username.encode("utf-8"); p = (password or "").encode("utf-8")
        if len(u) > 255 or len(p) > 255:
            raise RuntimeError("SOCKS5: creds too long")
        sock.sendall(bytes([1, len(u)]) + u + bytes([len(p)]) + p)
        a = sock.recv(2)
        if len(a) < 2 or a[1] != 0x00:
            raise RuntimeError("SOCKS5: auth failed")
    # CONNECT to 1.1.1.1:80
    dst = b"\x01\x01\x01\x01"  # 1.1.1.1
    port = (80).to_bytes(2, "big")
    req = bytes([5, 1, 0, 1]) + dst + port
    sock.sendall(req)
    rep = sock.recv(10)
    if len(rep) < 2 or rep[1] != 0x00:
        raise RuntimeError(f"SOCKS5: connect failed, rep={rep[1] if rep else '??'}")

def _http_connect(sock, host="www.google.com", port=443, timeout=5.0, username=None, password=None):
    sock.settimeout(timeout)
    hdrs = ""
    if username:
        import base64
        token = base64.b64encode(f"{username}:{password or ''}".encode()).decode()
        hdrs += f"Proxy-Authorization: Basic {token}\r\n"
    req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n{hdrs}\r\n"
    sock.sendall(req.encode("ascii"))
    data = sock.recv(1024)
    if not data.startswith(b"HTTP/1.1 200") and not data.startswith(b"HTTP/1.0 200"):
        # try to parse status
        try:
            status = data.split(b"\r\n",1)[0].decode("ascii", "ignore")
        except Exception:
            status = str(data[:32])
        raise RuntimeError(f"HTTP CONNECT failed: {status}")

from PyQt6 import QtWidgets, QtCore, QtGui
import socket
from app import db
from .login_dialog import LoginDialog
from .credentials_dialog import AccountCredentialsDialog
from .account_profile_dialog import AccountProfileDialog
from app.accounts import ACCOUNTS

class AccountsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QtWidgets.QVBoxLayout())

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Добавить (вход по телефону)")
        self.btn_import = QtWidgets.QPushButton("Импортировать .session")
        self.btn_delete = QtWidgets.QPushButton("Удалить")
        self.btn_enable = QtWidgets.QPushButton("Включить")
        self.btn_disable = QtWidgets.QPushButton("Выключить")
        self.btn_proxy = QtWidgets.QPushButton("Проверить прокси")
        self.btn_profile = QtWidgets.QPushButton("Профиль…")
        btn_row.addWidget(self.btn_add); btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_delete); btn_row.addWidget(self.btn_enable); btn_row.addWidget(self.btn_disable); btn_row.addWidget(self.btn_proxy); btn_row.addWidget(self.btn_profile)
        self.layout().addLayout(btn_row)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Телефон","Статус"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout().addWidget(self.table, 1)

        self.btn_add.clicked.connect(self.add_account)
        self.btn_import.clicked.connect(self.import_sessions)
        self.btn_delete.clicked.connect(self.delete_account)
        self.btn_enable.clicked.connect(self.enable_account)
        self.btn_disable.clicked.connect(self.disable_account)
        self.btn_proxy.clicked.connect(self.check_proxy)
        self.btn_profile.clicked.connect(self.edit_profile)

        self.refresh()

    def refresh(self):
        rows = list(db.list_accounts())
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(r["phone"]))  # assumes dict-like
            status = "Включен" if int((r["enabled"] if hasattr(r,"keys") and "enabled" in r.keys() else 0) or 0) else "Выключен"
            item = QtWidgets.QTableWidgetItem(status)
            try:
                item.setForeground(QtGui.QBrush(QtGui.QColor("limegreen" if status=="Включен" else "gray")))
            except Exception:
                pass
            self.table.setItem(i, 1, item)

    def _selected_phone(self):
        row = self.table.currentRow()
        if row < 0: return None
        item = self.table.item(row, 0)
        return item.text() if item else None

    def add_account(self):
        dlg = LoginDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()

    def import_sessions(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Выберите .session файлы", "", "Telethon sessions (*.session)")
        if not files: return
        imported = []
        for path in files:
            try:
                phone = ACCOUNTS.import_session_file(path)
                imported.append(phone)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Импорт", f"{path}: {e}")
        # для каждого импортированного номера запросим API id/hash и сохраним пер-аккаунтно
        for ph in imported:
            cred = AccountCredentialsDialog(ph, self)
            if cred.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                if not cred.save():
                    # если не сохранили валидно — повторим запрос
                    QtWidgets.QMessageBox.warning(self, "API", "Данные не сохранены. Ещё раз открою форму." )
                    if cred.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                        if not cred.save():
                            QtWidgets.QMessageBox.critical(self, "API", "Без корректных API ID/Hash аккаунт не запустится.")
            else:
                QtWidgets.QMessageBox.information(self, "API", f"Для {ph} можно указать API позже во вкладке 'Настройки' или при запуске.")
        self.refresh()

    def delete_account(self):
        phone = self._selected_phone()
        if not phone: return
        try:
            db.delete_account(phone)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", str(e))
        finally:
            self.refresh()

    def enable_account(self):
        phone = self._selected_phone()
        if not phone: return
        try:
            ACCOUNTS.start_account(phone); self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", str(e))

    def disable_account(self):
        phone = self._selected_phone()
        if not phone: return
        ACCOUNTS.stop_account(phone); self.refresh()


    def edit_profile(self):
        phone = self._selected_phone()
        if not phone: return
        dlg = AccountProfileDialog(phone, self)
        dlg.exec()


    
def check_proxy(self):
    from app import db
    phone = self._selected_phone()
    if not phone:
        QtWidgets.QMessageBox.warning(self, "Прокси", "Сначала выберите аккаунт.")
        return
    try:
        pr = db.get_account_proxy(phone)
        enabled = int(pr.get("enabled", 0)) if pr else 0
        host = str((pr or {}).get("host") or "").strip()
        port = int(str((pr or {}).get("port") or "0"))
        ptype = ((pr or {}).get("type","socks5") or "socks5").lower()
        username = (pr or {}).get("username") or None
        password = (pr or {}).get("password") or None
        if not enabled:
            QtWidgets.QMessageBox.information(self, "Прокси", "Прокси для этого аккаунта отключён.")
            return
        if not host or not port:
            QtWidgets.QMessageBox.critical(self, "Прокси", f"Неверные параметры: host={host!r} port={port!r}")
            return
        ok = False
        err_text = ""
        try:
            s = socket.create_connection((host, port), timeout=4.0)
            if ptype == "socks5":
                _socks5_handshake(s, username=username, password=password, timeout=5.0)
            else:
                _http_connect(s, timeout=5.0, username=username, password=password)
            s.close()
            ok = True
        except Exception as e:
            err_text = str(e)
        if ok:
            QtWidgets.QMessageBox.information(self, "Прокси", f"Прокси {ptype.upper()} на {host}:{port} — OK (рукопожатие прошло).")
        else:
            QtWidgets.QMessageBox.critical(self, "Прокси", f"Прокси не работает или отверг рукопожатие:\n{ptype.upper()} {host}:{port}\n{err_text}")
    except Exception as e:
        QtWidgets.QMessageBox.critical(self, "Прокси", f"Ошибка проверки прокси: {e}")


def _accounts_tab_check_proxy(self):
    from app import db
    phone = self._selected_phone()
    if not phone:
        QtWidgets.QMessageBox.warning(self, "Прокси", "Сначала выберите аккаунт.")
        return
    try:
        pr = db.get_account_proxy(phone) or {}
        enabled = int(pr.get("enabled", 0) or 0)
        host = (pr.get("host") or "").strip()
        port = int(str(pr.get("port") or "0"))
        ptype = (pr.get("type") or "socks5").lower()
        username = pr.get("username") or None
        password = pr.get("password") or None
        if not enabled:
            QtWidgets.QMessageBox.information(self, "Прокси", "Прокси для этого аккаунта отключён.")
            return
        if not host or not port:
            QtWidgets.QMessageBox.critical(self, "Прокси", f"Неверные параметры: host={host!r} port={port!r}")
            return
        ok = False
        err_text = ""
        try:
            s = socket.create_connection((host, port), timeout=4.0)
            if ptype == "socks5":
                _socks5_handshake(s, username=username, password=password, timeout=5.0)
            else:
                _http_connect(s, timeout=5.0, username=username, password=password)
            s.close()
            ok = True
        except Exception as e:
            err_text = str(e)
        if ok:
            QtWidgets.QMessageBox.information(self, "Прокси", f"Прокси {ptype.upper()} на {host}:{port} — OK (рукопожатие прошло).")
        else:
            QtWidgets.QMessageBox.critical(self, "Прокси", f"Прокси не работает или отверг рукопожатие:\n{ptype.upper()} {host}:{port}\n{err_text}")
    except Exception as e:
        QtWidgets.QMessageBox.critical(self, "Прокси", f"Ошибка проверки прокси: {e}")

# Safety: ensure AccountsTab has attr at import time
try:
    if 'AccountsTab' in globals() and not hasattr(AccountsTab, "check_proxy"):
        AccountsTab.check_proxy = _accounts_tab_check_proxy
except Exception:
    pass
