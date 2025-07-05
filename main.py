# main.py
import sys
import os
from PyQt5.QtWidgets import QApplication
from config import load_config
from gui.main_window import MainWindow
from utils.logger import get_logger, setup_development_logging

def main():
    # Инициализируем логирование
    logger = get_logger('main')
    logger.info("Запуск приложения 'Система контроля материалов'")
    
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

    # Загружаем конфиг (например, пути к БД и документам)
    try:
        cfg = load_config()
        logger.info("Конфигурация загружена успешно")
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        cfg = {}

    # В режиме отладки используем тестового администратора
    user = {
        'id': 1,
        'login': 'admin',
        'role': 'Администратор',
        'name': 'Админ'
    }
    logger.info(f"Запуск с пользователем: {user['login']} ({user['role']})")

    try:
        # Создаём и показываем главное окно
        win = MainWindow(user)
        win.show()
        logger.info("Главное окно создано и отображено")

        # Запускаем цикл обработки событий
        logger.info("Запуск главного цикла приложения")
        exit_code = app.exec_()
        logger.info(f"Приложение завершено с кодом: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
