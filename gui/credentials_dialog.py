from PyQt6 import QtWidgets
from app import db

class CredentialsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Telegram API Credentials")
        self.setMinimumWidth(420)
        layout = QtWidgets.QFormLayout(self)

        self.api_id = QtWidgets.QLineEdit()
        self.api_id.setPlaceholderText("App api_id (число)")
        self.api_hash = QtWidgets.QLineEdit()
        self.api_hash.setPlaceholderText("App api_hash (строка)")

        # preload current settings if any
        try:
            self.api_id.setText(db.get_setting("telegram_api_id","") or "")
            self.api_hash.setText(db.get_setting("telegram_api_hash","") or "")
        except Exception:
            pass

        layout.addRow("API ID:", self.api_id)
        layout.addRow("API Hash:", self.api_hash)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def save(self):
        aid = (self.api_id.text() or "").strip()
        ah = (self.api_hash.text() or "").strip()
        if not aid.isdigit() or not ah:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Введите корректные API ID (число) и API Hash (строка)." )
            return False
        db.set_setting("telegram_api_id", aid)
        db.set_setting("telegram_api_hash", ah)
        return True

class AccountCredentialsDialog(CredentialsDialog):
    def __init__(self, phone: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Telegram API для {phone}")
        self._phone = phone
        # preload per-account first
        try:
            aid, ah = db.get_account_api(phone)
            if aid: self.api_id.setText(str(aid))
            if ah: self.api_hash.setText(ah)
        except Exception:
            pass
        # if still empty, try global
        if not self.api_id.text():
            try: self.api_id.setText(db.get_setting("telegram_api_id","") or "")
            except Exception: pass
        if not self.api_hash.text():
            try: self.api_hash.setText(db.get_setting("telegram_api_hash","") or "")
            except Exception: pass

    def save(self):
        aid = (self.api_id.text() or "").strip()
        ah = (self.api_hash.text() or "").strip()
        if not aid.isdigit() or not ah:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Введите корректные API ID (число) и API Hash (строка)." )
            return False
        # save BOTH per-account and global defaults (so следующий телефон подхватит)
        db.set_account_api(self._phone, int(aid), ah)
        if not (db.get_setting("telegram_api_id","") and db.get_setting("telegram_api_hash","")):
            db.set_setting("telegram_api_id", aid)
            db.set_setting("telegram_api_hash", ah)
        return True
