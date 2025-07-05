from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from PyQt5.QtCore import Qt
from db.database import Database
from gui.main_window import MainWindow

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Вход в систему контроля материалов')
        self.db = Database()
        self.db.connect()
        self.db.initialize_schema()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.label_login = QLabel('Логин:')
        self.edit_login = QLineEdit()
        layout.addWidget(self.label_login)
        layout.addWidget(self.edit_login)

        self.label_pass = QLabel('Пароль:')
        self.edit_pass = QLineEdit()
        self.edit_pass.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.label_pass)
        layout.addWidget(self.edit_pass)

        self.btn_login = QPushButton('Войти')
        self.btn_login.clicked.connect(self._handle_login)
        layout.addWidget(self.btn_login)

        self.setLayout(layout)

    def _handle_login(self):
        login = self.edit_login.text().strip()
        password = self.edit_pass.text().strip()
        user = self.db.verify_user(login, password)
        if user:
            QMessageBox.information(self, 'Успех', f'Добро пожаловать, {user["name"] or user["login"]}!')
            self.open_main(user)
        else:
            QMessageBox.warning(self, 'Ошибка', 'Неверный логин или пароль')

    def open_main(self, user_row):
        self.main_win = MainWindow(user_row)
        self.main_win.show()
        self.close()
