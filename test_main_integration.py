#!/usr/bin/env python
"""
Тестовый скрипт для проверки интеграции UX систем в основное приложение.
Этот скрипт запускает основное приложение с UX системами для тестирования.
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Устанавливаем переменную окружения для тестового режима
os.environ['TEST_MODE'] = 'true'

def main():
    """Запуск основного приложения в тестовом режиме."""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ UX СИСТЕМ")
    print("=" * 60)
    print()
    print("Приложение запускается в тестовом режиме:")
    print("- Автоматический вход под администратором")
    print("- Интеграция всех UX систем")
    print("- Tooltips, горячие клавиши, справка, undo/redo, автозаполнение")
    print()
    print("Для тестирования:")
    print("- Нажмите F1 для открытия справки")
    print("- Используйте Ctrl+Z/Y для undo/redo")
    print("- Попробуйте ввести текст в поле поиска (автозаполнение)")
    print("- Наведите курсор на элементы интерфейса (tooltips)")
    print("- Нажмите F5 для обновления данных")
    print()
    print("Запуск...")
    print()
    
    try:
        # Импортируем и запускаем основное приложение
        from main import main as main_app
        main_app()
    except KeyboardInterrupt:
        print("\nПриложение остановлено пользователем")
    except Exception as e:
        print(f"Ошибка при запуске приложения: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 