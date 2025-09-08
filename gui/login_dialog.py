import logging
from PyQt6 import QtWidgets, QtCore
from typing import Optional
from pathlib import Path
from app.paths import data_dir, sessions_dir
import asyncio

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError, FloodWaitError
from app import db

DATA_DIR = data_dir()
SESSIONS_DIR = sessions_dir()

def _normalize_phone(p: str) -> str:
    p = (p or "").strip()
    if not p.startswith("+"):
        p = "+" + p
    return p

class LoginThread(QtCore.QThread):
    status = QtCore.pyqtSignal(str)
    need_code = QtCore.pyqtSignal()
    need_password = QtCore.pyqtSignal()
    success = QtCore.pyqtSignal(str, str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, api_id: int, api_hash: str, phone: str, parent=None):
        super().__init__(parent)
        self.api_id = int(api_id); self.api_hash = api_hash; self.phone = _normalize_phone(phone)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._code_fut: Optional[asyncio.Future] = None
        self._pwd_fut: Optional[asyncio.Future] = None

    def provide_code(self, code: str):
        if self._loop and self._code_fut and not self._code_fut.done():
            self._loop.call_soon_threadsafe(self._code_fut.set_result, code.strip())

    def provide_password(self, pwd: str):
        if self._loop and self._pwd_fut and not self._pwd_fut.done():
            self._loop.call_soon_threadsafe(self._pwd_fut.set_result, pwd)

    async def _get_code(self) -> str:
        self.need_code.emit()
        self._code_fut = self._loop.create_future()
        code = await self._code_fut
        return code

    async def _get_pwd(self) -> str:
        self.need_password.emit()
        self._pwd_fut = self._loop.create_future()
        pwd = await self._pwd_fut
        return pwd

    def run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            async def main():
                client = None
                try:
                    session_path = SESSIONS_DIR / f"{self.phone}.session"
                    client = TelegramClient(str(session_path), self.api_id, self.api_hash)
                    await client.connect()
                    self.status.emit("Подключение к Telegram...")
                    if not await client.is_user_authorized():
                        self.status.emit("Отправляю код...")
                        await client.send_code_request(self.phone)
                        while True:
                            code = await self._get_code()
                            try:
                                await client.sign_in(phone=self.phone, code=code)
                                break
                            except PhoneCodeInvalidError:
                                self.status.emit("Код неверный. Попробуйте ещё раз.")
                                continue
                            except PhoneCodeExpiredError:
                                self.status.emit("Код истёк. Отправляю новый...")
                                await client.send_code_request(self.phone)
                                continue
                            except SessionPasswordNeededError:
                                pwd = await self._get_pwd()
                                await client.sign_in(password=pwd)
                                break
                            except FloodWaitError as e:
                                raise RuntimeError(f"FloodWait: подождите {e.seconds} сек и попробуйте снова.")
                    # success
                    db.add_account(self.phone, str(session_path))
                    db.set_setting("telegram_api_id", str(self.api_id))
                    db.set_setting("telegram_api_hash", self.api_hash)
                    self.status.emit("Авторизация успешна.")
                    self.success.emit(self.phone, str(session_path))
                except Exception as e:
                    self.failed.emit(f"{type(e).__name__}: {e}")
                finally:
                    try:
                        if client:
                            await client.disconnect()
                    except Exception:
                        pass
            self._loop.run_until_complete(main())
            self._loop.close()
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")

class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход в Telegram (Telethon)")
        self.setModal(True)
        self.resize(540, 460)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.api_id = QtWidgets.QLineEdit(db.get_setting("telegram_api_id",""))
        self.api_hash = QtWidgets.QLineEdit(db.get_setting("telegram_api_hash",""))
        self.phone = QtWidgets.QLineEdit()
        self.code = QtWidgets.QLineEdit(); self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.code.setEnabled(False); self.password.setVisible(False)
        self.phone.setPlaceholderText("+380XXXXXXXXX")
        form.addRow("API ID:", self.api_id); form.addRow("API Hash:", self.api_hash); form.addRow("Телефон:", self.phone)
        form.addRow("Код:", self.code); form.addRow("Пароль 2FA:", self.password)
        lay.addLayout(form)

        self.status = QtWidgets.QPlainTextEdit(); self.status.setReadOnly(True); lay.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("Отправить код")
        self.btn_submit = QtWidgets.QPushButton("Подтвердить / Войти")
        self.btn_cancel = QtWidgets.QPushButton("Отмена")
        row.addWidget(self.btn_start); row.addWidget(self.btn_submit); row.addStretch(1); row.addWidget(self.btn_cancel)
        lay.addLayout(row)

        self.worker: Optional[LoginThread] = None

        self.btn_start.clicked.connect(self._on_send_code)
        self.btn_submit.clicked.connect(self._on_submit)
        self.btn_cancel.clicked.connect(self.reject)

    def log(self, t: str): self.status.appendPlainText(t)

    def _on_send_code(self):
        api_id = self.api_id.text().strip(); api_hash = self.api_hash.text().strip(); phone = self.phone.text().strip()
        if not (api_id and api_hash and phone):
            QtWidgets.QMessageBox.warning(self, "Проверка", "Заполните API ID, API Hash и Телефон."); return
        try: int(api_id)
        except: QtWidgets.QMessageBox.warning(self, "Проверка", "API ID должен быть числом."); return
        self.worker = LoginThread(int(api_id), api_hash, phone, self)
        self.worker.status.connect(self.log)
        self.worker.need_code.connect(lambda: (self.code.setEnabled(True), self.code.setFocus()))
        self.worker.need_password.connect(lambda: (self.password.setVisible(True), self.password.setFocus()))
        self.worker.success.connect(self._on_success)
        self.worker.failed.connect(self._on_failed)
        # блокируем повторные нажатия, чтобы не сломать поток
        self.btn_start.setEnabled(False)
        self.worker.start()
        self.log("Процесс авторизации запущен...")

    def _on_submit(self):
        if not self.worker:
            QtWidgets.QMessageBox.information(self, "Инфо", "Сначала нажмите 'Отправить код'."); return
        if self.code.isEnabled() and self.code.text().strip():
            self.worker.provide_code(self.code.text().strip()); self.log("Код подтверждения отправлен.")
            self.code.clear()
        if self.password.isVisible() and self.password.text():
            self.worker.provide_password(self.password.text()); self.password.clear()

    def _on_success(self, phone, session_path):
        QtWidgets.QMessageBox.information(self, "Готово", f"Аккаунт {phone} успешно авторизован.")
        self.accept()

    def _on_failed(self, err):
        self.btn_start.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Ошибка", err)
        self.log(f"Ошибка: {err}")
