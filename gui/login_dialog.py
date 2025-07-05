import hashlib
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
)
from db.database import Database

class LoginDialog(QDialog):
    """
    Диалог для аутентификации пользователя:
    Запрашивает логин и пароль, проверяет в БД и возвращает роль и данные пользователя.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Вход в систему')
        self.user = None
        # Подключение к БД
        self.db = Database()
        self.db.connect()
        self._build()

    def _build(self):
        form = QFormLayout()
        # Поле логина
        self.login_edit = QLineEdit()
        form.addRow('Логин:', self.login_edit)
        # Поле пароля
        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        form.addRow('Пароль:', self.pwd_edit)
        # Кнопки ОК/Отмена
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setLayout(form)

    def _on_accept(self):
        login = self.login_edit.text().strip()
        pwd = self.pwd_edit.text()
        if not login or not pwd:
            QMessageBox.warning(self, 'Ошибка', 'Укажите логин и пароль')
            return
        # Проверка в БД: пароль хранится как SHA256
        cur = self.db.conn.cursor()
        cur.execute('SELECT id, role, password_hash, name FROM Users WHERE login=?', (login,))
        row = cur.fetchone()
        if not row:
            QMessageBox.critical(self, 'Ошибка', 'Неверный логин или пароль')
            return
        # Хешируем введённый пароль
        h = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
        if h != row['password_hash']:
            QMessageBox.critical(self, 'Ошибка', 'Неверный логин или пароль')
            return
        # Успешная авторизация
        self.user = {'id': row['id'], 'login': login, 'role': row['role'], 'name': row['name']}
        self.accept()

    def get_user(self):
        return self.user
