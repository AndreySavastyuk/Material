# Система обработки ошибок

Современная система обработки ошибок для проекта "Система контроля материалов" с централизованным управлением, user-friendly сообщениями и детальным логированием.

## Содержание

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Иерархия исключений](#иерархия-исключений)
- [Декораторы](#декораторы)
- [Использование в GUI](#использование-в-gui)
- [Интеграция с существующим кодом](#интеграция-с-существующим-кодом)
- [Примеры использования](#примеры-использования)
- [Конфигурация](#конфигурация)
- [Тестирование](#тестирование)

## Обзор

Система обработки ошибок предоставляет:

✅ **Иерархию кастомных исключений** с детальной информацией  
✅ **Централизованный обработчик ошибок** с умной обработкой  
✅ **Декораторы для автоматической обработки** в GUI и сервисах  
✅ **User-friendly сообщения** для пользователей  
✅ **Детальное логирование** с разными уровнями  
✅ **Интеграцию с системой аудита** для критических ошибок  
✅ **Подавление повторяющихся ошибок**  
✅ **Предложения по исправлению** для каждого типа ошибок

## Архитектура

```
utils/
├── exceptions.py          # Иерархия исключений
├── error_handlers.py      # Декораторы и обработчики
└── logger.py             # Интеграция с логированием

gui/
├── admin/
│   └── suppliers_new.py  # Пример использования в GUI
└── ...

services/
├── base.py              # Обновленный базовый сервис
└── ...

tests/
├── test_exceptions.py      # Тесты исключений
├── test_error_handlers.py  # Тесты обработчиков
└── ...
```

## Иерархия исключений

### Базовое исключение

```python
from utils.exceptions import BaseApplicationError

error = BaseApplicationError(
    message="Техническое сообщение",
    error_code="CUSTOM_001",
    severity=ErrorSeverity.HIGH,
    category=ErrorCategory.SYSTEM,
    details={"key": "value"},
    user_message="Понятное сообщение для пользователя",
    suggestions=["Попробуйте это", "Проверьте то"],
    original_error=original_exception
)
```

### Категории ошибок

| Категория            | Описание         | Примеры                              |
| -------------------- | ---------------- | ------------------------------------ |
| **VALIDATION**       | Ошибки валидации | Пустые поля, неверный формат         |
| **DATABASE**         | Ошибки БД        | Нарушение связей, дублирование       |
| **BUSINESS_LOGIC**   | Бизнес-логика    | Недостаток прав, используемая запись |
| **NETWORK**          | Сетевые ошибки   | Таймауты, недоступность сервиса      |
| **FILE_SYSTEM**      | Файловая система | Файл не найден, нет прав доступа     |
| **AUTHENTICATION**   | Аутентификация   | Неверные учетные данные              |
| **AUTHORIZATION**    | Авторизация      | Недостаток прав доступа              |
| **CONFIGURATION**    | Конфигурация     | Отсутствие настроек                  |
| **EXTERNAL_SERVICE** | Внешние сервисы  | Ошибки Telegram, API                 |
| **SYSTEM**           | Системные ошибки | Общие системные сбои                 |

### Уровни серьезности

| Уровень      | Описание           | Поведение                  |
| ------------ | ------------------ | -------------------------- |
| **LOW**      | Информационные     | Простое уведомление        |
| **MEDIUM**   | Обычные ошибки     | Стандартное сообщение      |
| **HIGH**     | Важные ошибки      | Детальный диалог           |
| **CRITICAL** | Критические ошибки | Развернутый диалог + аудит |

## Декораторы

### Декоратор для GUI

```python
from utils.error_handlers import handle_gui_errors

class MyWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.user = {'login': 'admin', 'role': 'admin'}

    @handle_gui_errors(context="add_supplier")
    def add_supplier(self):
        # Код может вызвать исключение
        supplier_name = self.get_supplier_name()
        if not supplier_name:
            raise RequiredFieldError("Название поставщика обязательно")

        # Обработка будет автоматической
        self.save_supplier(supplier_name)
```

### Декоратор для БД

```python
from utils.error_handlers import handle_database_errors

class SupplierRepository:
    @handle_database_errors("создание поставщика")
    def create_supplier(self, name: str) -> int:
        # SQLite ошибки автоматически преобразуются в кастомные
        cursor = self.conn.execute(
            "INSERT INTO Suppliers (name) VALUES (?)",
            (name,)
        )
        return cursor.lastrowid
```

### Декоратор для валидации

```python
from utils.error_handlers import handle_validation_errors

class DataValidator:
    @handle_validation_errors
    def validate_email(self, email: str) -> bool:
        # ValueError автоматически преобразуется в ValidationError
        if "@" not in email:
            raise ValueError("Неверный формат email")
        return True
```

## Использование в GUI

### Простые сообщения

```python
from utils.error_handlers import show_error, show_warning, show_info, confirm_action

# Быстрые сообщения
show_error("Ошибка сохранения данных", parent=self)
show_warning("Внимание! Данные будут потеряны", parent=self)
show_info("Операция выполнена успешно", parent=self)

# Подтверждение
if confirm_action("Удалить выбранную запись?", parent=self):
    self.delete_record()
```

### Детальные диалоги

```python
from utils.error_handlers import ErrorDialog

# Для показа детальной информации об ошибке
error = ValidationError(
    "Неверные данные",
    field_name="email",
    suggestions=["Проверьте формат email", "Используйте корректный домен"]
)

dialog = ErrorDialog(error, parent=self)
dialog.exec_()
```

### Успешные операции

```python
from utils.error_handlers import show_success_message

# Автоматическое закрытие через 3 секунды
show_success_message(
    "Успех",
    "Поставщик успешно добавлен",
    parent=self,
    auto_close=3
)
```

## Интеграция с существующим кодом

### Обновление GUI компонентов

**Было:**

```python
def add_supplier(self):
    try:
        # код
    except Exception as e:
        QMessageBox.critical(self, 'Ошибка', str(e))
```

**Стало:**

```python
@handle_gui_errors(context="add_supplier")
def add_supplier(self):
    # код - обработка ошибок автоматическая
    pass
```

### Обновление сервисов

**Было:**

```python
def create_supplier(self, name: str):
    if not name:
        raise ValidationError("Название обязательно")
    # код
```

**Стало:**

```python
def create_supplier(self, name: str):
    if not name:
        raise RequiredFieldError("Название обязательно", field_name="name")
    # код
```

## Примеры использования

### Валидация данных

```python
from utils.exceptions import RequiredFieldError, ValueOutOfRangeError

def validate_material_data(data: dict):
    # Проверка обязательных полей
    if not data.get('name'):
        raise RequiredFieldError(
            "Название материала обязательно",
            field_name="name"
        )

    # Проверка диапазона
    thickness = data.get('thickness', 0)
    if thickness < 0.1 or thickness > 100:
        raise ValueOutOfRangeError(
            "Толщина вне допустимого диапазона",
            field_name="thickness",
            field_value=thickness,
            min_value=0.1,
            max_value=100,
            suggestions=[
                "Введите толщину от 0.1 до 100 мм",
                "Проверьте единицы измерения"
            ]
        )
```

### Бизнес-логика

```python
from utils.exceptions import RecordInUseError, InsufficientPermissionsError

def delete_supplier(self, supplier_id: int, user: dict):
    # Проверка прав
    if user['role'] != 'admin':
        raise InsufficientPermissionsError(
            "Недостаточно прав для удаления поставщика",
            required_permission="admin"
        )

    # Проверка использования
    materials_count = self.get_materials_count_by_supplier(supplier_id)
    if materials_count > 0:
        raise RecordInUseError(
            f"Поставщик используется в {materials_count} материалах",
            record_type="поставщик",
            used_in=["материалы"],
            suggestions=[
                "Сначала измените поставщика в материалах",
                "Используйте архивирование вместо удаления"
            ]
        )

    # Удаление
    self.repository.delete(supplier_id)
```

### Внешние сервисы

```python
from utils.exceptions import TelegramError, TimeoutError

def send_notification(self, message: str):
    try:
        response = requests.post(
            self.bot_url,
            json={'text': message},
            timeout=30
        )
        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise TimeoutError(
            "Превышено время ожидания ответа от Telegram",
            suggestions=[
                "Проверьте подключение к интернету",
                "Попробуйте позже"
            ]
        )
    except requests.exceptions.RequestException as e:
        raise TelegramError(
            f"Ошибка отправки уведомления: {e}",
            original_error=e,
            suggestions=[
                "Проверьте настройки Telegram бота",
                "Убедитесь в корректности токена"
            ]
        )
```

## Конфигурация

### Настройки обработчика ошибок

```python
from utils.error_handlers import error_handler

# Сброс счетчиков ошибок
error_handler.reset_error_counters()

# Получение статистики
stats = error_handler.get_error_statistics()
print(f"Всего ошибок: {sum(stats.values())}")

# Настройка подавления (автоматически после 3 повторений)
# Можно настроить в коде error_handler'а
```

### Интеграция с логированием

```python
from utils.logger import get_logger, log_audit

logger = get_logger('my_module')

# Логирование с контекстом
try:
    # операция
    pass
except Exception as e:
    logger.error(f"Ошибка в операции: {e}")

    # Аудит для критических операций
    log_audit(
        user_data={'login': 'admin'},
        action='error_occurred',
        object_id=0,
        description=f"Критическая ошибка: {e}"
    )
```

## Тестирование

### Запуск тестов

```bash
# Все тесты системы ошибок
pytest tests/test_exceptions.py tests/test_error_handlers.py -v

# Тесты исключений
pytest tests/test_exceptions.py::TestBaseApplicationError -v

# Тесты обработчиков
pytest tests/test_error_handlers.py::TestErrorHandler -v

# Интеграционные тесты
pytest tests/test_error_handlers.py::TestErrorHandlerIntegration -v
```

### Покрытие кода

```bash
# Проверка покрытия
pytest --cov=utils.exceptions --cov=utils.error_handlers tests/

# Отчет в HTML
pytest --cov=utils.exceptions --cov=utils.error_handlers --cov-report=html tests/
```

### Структура тестов

- **test_exceptions.py** - 23 теста для иерархии исключений
- **test_error_handlers.py** - 20 тестов для обработчиков и декораторов
- **Интеграционные тесты** - проверка работы всей системы

## Обратная совместимость

Система полностью обратно совместима:

```python
# Старый код продолжит работать
from services.base import ServiceError, ValidationError, NotFoundError

# Новый код использует расширенную функциональность
from utils.exceptions import BaseApplicationError, RequiredFieldError
```

## Преимущества новой системы

1. **Унифицированная обработка** - все ошибки обрабатываются одинаково
2. **Детальная информация** - каждая ошибка содержит контекст и предложения
3. **User-friendly сообщения** - понятные сообщения для пользователей
4. **Автоматическое логирование** - все ошибки попадают в логи
5. **Интеграция с аудитом** - критические ошибки записываются в аудит
6. **Подавление повторов** - избегание спама одинаковых ошибок
7. **Простота использования** - декораторы упрощают применение
8. **Расширяемость** - легко добавлять новые типы ошибок

## Лучшие практики

1. **Используйте специфичные исключения** вместо общих
2. **Добавляйте предложения** по исправлению ошибок
3. **Применяйте декораторы** для автоматической обработки
4. **Логируйте контекст** для упрощения отладки
5. **Тестируйте обработку ошибок** наравне с основной логикой
6. **Используйте user-friendly сообщения** для пользователей
7. **Обрабатывайте ошибки на правильном уровне** (GUI, сервисы, репозитории)

---

**Система обработки ошибок готова к использованию в продакшене!** 🚀
