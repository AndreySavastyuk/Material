# main.py
import sys
import os
from PyQt5.QtWidgets import QApplication
from config import load_config
from gui.main_window import MainWindow

def main():
    # Создаём приложение
    app = QApplication(sys.argv)

    # Подгружаем QSS-тему
    qss_path = os.path.join(os.path.dirname(__file__), 'style.qss')
    if os.path.isfile(qss_path):
        with open(qss_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())

    # Загружаем конфиг (например, пути к БД и документам)
    cfg = load_config()

    # В режиме отладки используем тестового администратора
    user = {
        'id': 1,
        'login': 'admin',
        'role': 'Администратор',
        'name': 'Админ'
    }

    # Создаём и показываем главное окно
    win = MainWindow(user)
    win.show()

    # Запускаем цикл обработки событий
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
