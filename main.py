#!/usr/bin/env python
"""
Главный файл приложения с интеграцией системы ролей и прав доступа.
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from config import load_config
from gui.login_dialog import LoginDialog
from gui.main_window_with_roles import RoleBasedMainWindow
from db.database import Database
from services.authorization_service import AuthorizationService
from utils.logger import get_logger, setup_development_logging
from utils.exceptions import AuthenticationError


def main():
    """Главная функция приложения."""
    # Инициализируем логирование
    logger = get_logger('main')
    logger.info("Запуск приложения 'Система контроля материалов' с системой ролей")
    
    # Настраиваем уровень логирования для разработки
    setup_development_logging()
    
    # Создаём приложение
    app = QApplication(sys.argv)
    logger.info("QApplication создано")

    # Подгружаем QSS-тему
    qss_path = os.path.join(os.path.dirname(__file__), 'style.qss')
    if os.path.isfile(qss_path):
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())
            logger.info(f"QSS стили загружены из {qss_path}")
        except Exception as e:
            logger.error(f"Ошибка загрузки QSS стилей: {e}")
    else:
        logger.warning(f"Файл стилей не найден: {qss_path}")

    # Загружаем конфиг
    try:
        cfg = load_config()
        logger.info("Конфигурация загружена успешно")
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        cfg = {}

    # Инициализируем базу данных и сервис авторизации
    try:
        db = Database()
        db.connect()
        auth_service = AuthorizationService(db)
        logger.info("База данных и сервис авторизации инициализированы")
    except Exception as e:
        logger.critical(f"Ошибка инициализации базы данных: {e}")
        QMessageBox.critical(None, "Ошибка", f"Не удалось подключиться к базе данных:\n{e}")
        sys.exit(1)

    # В режиме отладки можем использовать прямой вход
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    if DEBUG_MODE:
        logger.info("Режим отладки - используем прямой вход для администратора")
        try:
            user = auth_service.authenticate_user('admin', 'admin')
            logger.info(f"Отладочный вход выполнен: {user['login']}")
        except AuthenticationError:
            logger.warning("Не удалось выполнить отладочный вход, переходим к обычной авторизации")
            user = None
    else:
        user = None

    # Если пользователь не авторизован, показываем диалог входа
    if not user:
        login_dialog = LoginDialog(auth_service)
        if login_dialog.exec_() == LoginDialog.Accepted:
            user = login_dialog.get_authenticated_user()
            session_token = login_dialog.get_session_token()
            logger.info(f"Пользователь авторизован: {user['login']}, токен сессии: {session_token[:10]}...")
        else:
            logger.info("Авторизация отменена пользователем")
            sys.exit(0)

    # Получаем роли и права пользователя
    user_roles = db.get_user_roles(user['id'])
    user_permissions = db.get_user_permissions(user['id'])
    
    logger.info(f"Пользователь {user['login']} имеет {len(user_roles)} ролей и {len(user_permissions)} прав")
    
    # Логируем роли для отладки
    role_names = [role['name'] for role in user_roles]
    logger.info(f"Роли пользователя: {', '.join(role_names)}")

    try:
        # Создаём и показываем главное окно с системой ролей
        win = RoleBasedMainWindow(user, auth_service)
        win.show()
        logger.info("Главное окно с системой ролей создано и отображено")

        # Запускаем цикл обработки событий
        logger.info("Запуск главного цикла приложения")
        exit_code = app.exec_()
        logger.info(f"Приложение завершено с кодом: {exit_code}")
        
        # Закрываем соединение с базой данных
        db.close()
        logger.info("Соединение с базой данных закрыто")
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}")
        QMessageBox.critical(None, "Критическая ошибка", 
                           f"Произошла критическая ошибка:\n{e}\n\nПриложение будет закрыто.")
        sys.exit(1)


if __name__ == '__main__':
    main()
