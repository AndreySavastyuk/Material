#!/usr/bin/env python
"""
Главный файл приложения с интеграцией системы ролей и прав доступа.
Включает UX системы: tooltips, горячие клавиши, справку, undo/redo, автозаполнение.
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
from utils.enhanced_logger import (
    initialize_logging, get_enhanced_logger, performance_monitor,
    log_user_action, log_database_operation, log_error_with_context
)
from utils.exceptions import AuthenticationError


def main():
    """Главная функция приложения."""
    # Инициализируем расширенное логирование
    log_manager = initialize_logging("MaterialControl", "logs", enable_performance=True)
    logger = get_enhanced_logger('main')
    
    logger.info("=" * 70)
    logger.info("ЗАПУСК ПРИЛОЖЕНИЯ 'Система контроля материалов' v2.0 + UX Systems")
    logger.info("=" * 70)
    
    # Настраиваем уровень логирования для разработки (обратная совместимость)
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
        log_database_operation("connect", "database", 0, 0)
    except Exception as e:
        logger.critical(f"Ошибка инициализации базы данных: {e}")
        log_error_with_context(e, "database_initialization")
        QMessageBox.critical(None, "Ошибка", f"Не удалось подключиться к базе данных:\n{e}")
        sys.exit(1)

    # ЗАГЛУШКА ДЛЯ ТЕСТИРОВАНИЯ - автоматический вход под администратором
    TEST_MODE = os.getenv('TEST_MODE', 'true').lower() == 'true'
    
    if TEST_MODE:
        logger.info("ТЕСТОВЫЙ РЕЖИМ - используем автоматический вход под администратором")
        try:
            # Попробуем войти под admin/admin
            user = auth_service.authenticate_user('admin', 'admin')
            logger.info(f"Автоматический вход выполнен: {user['login']}")
            log_user_action("test_auto_login", "TestMode", {"user": user['login']}, user['login'])
        except AuthenticationError:
            try:
                # Если admin/admin не работает, попробуем создать временного администратора
                logger.info("Создаем временного администратора для тестирования")
                # Здесь можно добавить создание временного пользователя
                # Пока что используем стандартную авторизацию
                user = None
            except Exception as e:
                logger.warning(f"Не удалось создать временного администратора: {e}")
                user = None
    else:
        user = None

    # Если пользователь не авторизован, показываем диалог входа
    if not user:
        login_dialog = LoginDialog(auth_service)
        if login_dialog.exec_() == LoginDialog.Accepted:
            user = login_dialog.get_authenticated_user()
            session_token = user.get('session_token')
            
            user_id = user.get('login', 'unknown')
            user_role = user.get('role', 'unknown')
            
            if session_token:
                logger.info(f"Пользователь авторизован: {user_id}, роль: {user_role}, токен сессии: {session_token[:10]}...")
            else:
                logger.info(f"Пользователь авторизован: {user_id}, роль: {user_role}")
            
            log_user_action("successful_login", "LoginDialog", {
                "user_role": user_role,
                "has_session_token": bool(session_token)
            }, user_id)
            
        else:
            logger.info("Авторизация отменена пользователем")
            log_user_action("login_cancelled", "LoginDialog", {})
            sys.exit(0)

    # Получаем роли и права пользователя
    user_roles = db.get_user_roles(user['id'])
    user_permissions = db.get_user_permissions(user['id'])
    
    logger.info(f"Пользователь {user['login']} имеет {len(user_roles)} ролей и {len(user_permissions)} прав")
    log_database_operation("select", "user_roles", len(user_roles), 0)
    log_database_operation("select", "user_permissions", len(user_permissions), 0)
    
    # Логируем роли для отладки
    role_names = [role['name'] for role in user_roles]
    logger.info(f"Роли пользователя: {', '.join(role_names)}")

    try:
        # Создаём и показываем главное окно с системой ролей и UX системами
        win = RoleBasedMainWindow(user, auth_service)
        win.show()
        logger.info("Главное окно с системой ролей и UX системами создано и отображено")
        log_user_action("main_window_opened", "RoleBasedMainWindow", {
            "user_roles": role_names,
            "ux_systems_enabled": True
        }, user['login'])

        # Запускаем цикл обработки событий
        logger.info("Запуск главного цикла приложения")
        exit_code = app.exec_()
        logger.info(f"Приложение завершено с кодом: {exit_code}")
        
        # Показываем сводку производительности при завершении
        try:
            perf_summary = log_manager.get_performance_summary()
            if perf_summary.get('total_calls', 0) > 0:
                logger.info("Сводка производительности за сессию", extra={'extra_data': perf_summary})
        except Exception as e:
            logger.warning(f"Не удалось получить сводку производительности: {e}")
        
        # Закрываем соединение с базой данных
        db.close()
        logger.info("Соединение с базой данных закрыто")
        log_database_operation("disconnect", "database", 0, 0)
        
        log_user_action("application_exit", "MainApplication", {
            "exit_code": exit_code
        }, user['login'])
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        log_error_with_context(e, "main_application_loop")
        QMessageBox.critical(None, "Критическая ошибка", 
                           f"Произошла критическая ошибка:\n{e}\n\nПриложение будет закрыто.")
        sys.exit(1)


if __name__ == '__main__':
    main()
