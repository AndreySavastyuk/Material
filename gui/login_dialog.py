import logging
import platform
import socket
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox, QLabel, QCheckBox
)
from PyQt5.QtCore import Qt
from services.authorization_service import AuthorizationService
from utils.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

class LoginDialog(QDialog):
    """
    Диалог для аутентификации пользователя с системой ролей и прав доступа.
    """
    def __init__(self, auth_service: AuthorizationService, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Вход в систему')
        self.setFixedSize(300, 200)
        self.auth_service = auth_service
        self.user = None
        self._build()

    def _build(self):
        """Создание интерфейса диалога."""
        form = QFormLayout()
        
        # Заголовок
        title = QLabel('Система контроля материалов')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        form.addRow(title)
        
        # Поле логина
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText('Введите логин')
        form.addRow('Логин:', self.login_edit)
        
        # Поле пароля
        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        self.pwd_edit.setPlaceholderText('Введите пароль')
        form.addRow('Пароль:', self.pwd_edit)
        
        # Чекбокс "Запомнить меня"
        self.remember_me_check = QCheckBox('Запомнить меня на этом устройстве')
        self.remember_me_check.setToolTip('Сохранить вход в систему на 30 дней')
        form.addRow(self.remember_me_check)
        
        # Обработка Enter
        self.login_edit.returnPressed.connect(self._on_accept)
        self.pwd_edit.returnPressed.connect(self._on_accept)
        
        # Кнопки ОК/Отмена
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Войти')
        buttons.button(QDialogButtonBox.Cancel).setText('Отмена')
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        
        self.setLayout(form)
        
        # Фокус на поле логина
        self.login_edit.setFocus()

    def _get_local_ip(self) -> str:
        """Получает локальный IP-адрес."""
        try:
            # Создаем сокет для определения IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _get_user_agent(self) -> str:
        """Получает информацию о системе."""
        try:
            return f"Material Control Desktop/{platform.system()} {platform.release()}"
        except Exception:
            return "Material Control Desktop/Unknown"

    def _on_accept(self):
        """Обработка нажатия кнопки входа."""
        login = self.login_edit.text().strip()
        pwd = self.pwd_edit.text()
        remember_me = self.remember_me_check.isChecked()
        
        if not login or not pwd:
            QMessageBox.warning(self, 'Ошибка', 'Укажите логин и пароль')
            return
            
        try:
            # Получаем информацию о сессии
            ip_address = self._get_local_ip()
            user_agent = self._get_user_agent()
            
            # Используем новый сервис авторизации с параметрами сессии
            user_data = self.auth_service.authenticate_user(
                login=login, 
                password=pwd,
                remember_me=remember_me,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if user_data:
                self.user = user_data
                
                # Получаем роли пользователя для отображения
                user_roles = self.auth_service.db.get_user_roles(user_data['id'])
                role_names = [role['display_name'] for role in user_roles]
                
                # Логируем информацию о сессии
                session_info = f"сессия до {user_data.get('session_expires_at', 'неизвестно')}"
                if remember_me:
                    session_info += " (запомнить меня)"
                
                logger.info(f"Успешная авторизация пользователя {login} с ролями: {', '.join(role_names)}, {session_info}")
                self.accept()
            else:
                QMessageBox.critical(self, 'Ошибка', 'Неверный логин или пароль')
                
        except AuthenticationError as e:
            logger.warning(f"Неудачная попытка авторизации пользователя {login}: {e}")
            QMessageBox.critical(self, 'Ошибка авторизации', str(e))
            
        except Exception as e:
            logger.error(f"Ошибка при авторизации пользователя {login}: {e}")
            QMessageBox.critical(self, 'Ошибка', 'Произошла ошибка при авторизации')

    def get_authenticated_user(self):
        """Возвращает данные авторизованного пользователя."""
        return self.user

    def get_user(self):
        """Совместимость со старым API."""
        return self.user
