# Новая архитектура проекта "Система контроля материалов"

## Описание

Этот документ описывает новую архитектуру проекта после рефакторинга от монолитного приложения к структуре с разделением на слои.

## Новая структура проекта

```
material_control_app/
├── db/                     # Старый слой БД (постепенно заменяется)
├── gui/                    # Графический интерфейс
├── repositories/           # Новый слой работы с БД
│   ├── __init__.py
│   └── base.py            # Базовый класс для всех репозиториев
├── services/               # Новый сервисный слой (бизнес-логика)
│   ├── __init__.py
│   └── base.py            # Базовый класс для всех сервисов
├── utils/                  # Вспомогательные утилиты
│   ├── __init__.py
│   └── config.py          # Улучшенное управление конфигурацией
├── migrations/             # Миграции БД
│   ├── __init__.py
│   └── 001_initial_schema.py
├── tests/                  # Тесты
│   ├── __init__.py
│   ├── conftest.py        # Конфигурация pytest
│   ├── test_base_repository.py
│   └── test_base_service.py
├── pytest.ini             # Конфигурация pytest
└── README_REFACTORING.md   # Этот файл
```

## Принципы новой архитектуры

### 1. Разделение на слои

- **GUI** - только отображение и взаимодействие с пользователем
- **Services** - бизнес-логика, валидация, обработка ошибок
- **Repositories** - работа с БД, CRUD операции
- **Database** - подключение к БД, миграции

### 2. Зависимости

```
GUI → Services → Repositories → Database
```

### 3. Принципы SOLID

- **Single Responsibility** - каждый класс отвечает за одну задачу
- **Open/Closed** - открыт для расширения, закрыт для модификации
- **Liskov Substitution** - подклассы должны заменять базовые классы
- **Interface Segregation** - клиенты не должны зависеть от неиспользуемых методов
- **Dependency Inversion** - зависимость от абстракций, а не от конкретных классов

## Базовые классы

### BaseRepository

Базовый класс для всех репозиториев. Предоставляет стандартные CRUD операции:

```python
from repositories.base import BaseRepository

class MaterialRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "Materials"

    @property
    def primary_key(self) -> str:
        return "id"
```

**Основные методы:**

- `create(data)` - создание записи
- `get_by_id(id)` - получение по ID
- `get_all(filters)` - получение всех записей
- `update(id, data)` - обновление записи
- `delete(id)` - удаление записи
- `soft_delete(id)` - мягкое удаление
- `restore(id)` - восстановление
- `count(filters)` - подсчет записей
- `exists(id)` - проверка существования

### BaseService

Базовый класс для всех сервисов. Содержит валидацию и обработку ошибок:

```python
from services.base import BaseService

class MaterialService(BaseService):
    def create(self, data: Dict[str, Any]) -> int:
        # Валидация данных
        self.validate_required_fields(data, ['name', 'type'])
        self.validate_data_types(data, {'name': str, 'count': int})

        # Создание записи
        return self._repository.create(data)

    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        # Валидация данных
        # Обновление записи
        return self._repository.update(record_id, data)
```

**Основные методы валидации:**

- `validate_required_fields()` - проверка обязательных полей
- `validate_data_types()` - проверка типов данных
- `validate_string_length()` - проверка длины строк
- `validate_numeric_range()` - проверка числовых диапазонов
- `validate_date_format()` - проверка формата даты

## Тестирование

### Настройка pytest

Конфигурация в `pytest.ini`:

- Автоматическое обнаружение тестов
- Покрытие кода (цель: 80%+)
- Маркеры для категоризации тестов

### Фикстуры

В `tests/conftest.py`:

- `test_db_connection` - подключение к тестовой БД
- `clean_db` - очистка БД перед каждым тестом
- `test_repository` - тестовый репозиторий
- `test_service` - тестовый сервис
- Данные для тестирования (материалы, пользователи и т.д.)

### Запуск тестов

```bash
# Все тесты
pytest

# Только unit тесты
pytest -m unit

# Только тесты БД
pytest -m database

# С покрытием кода
pytest --cov=. --cov-report=html

# Медленные тесты
pytest -m slow

# Исключить медленные тесты
pytest -m "not slow"
```

## Миграции БД

### Структура миграции

```python
def up(connection: sqlite3.Connection) -> None:
    """Применение миграции."""
    pass

def down(connection: sqlite3.Connection) -> None:
    """Откат миграции."""
    pass

def get_version() -> str:
    """Версия миграции."""
    return "001"

def get_description() -> str:
    """Описание миграции."""
    return "Описание изменений"
```

### Применение миграций

```python
# Применение всех миграций
migration_manager.apply_all()

# Откат к определенной версии
migration_manager.rollback_to("001")
```

## Обработка ошибок

### Иерархия исключений

```python
ServiceError                    # Базовое исключение
├── ValidationError            # Ошибки валидации
├── NotFoundError             # Запись не найдена
└── BusinessLogicError        # Нарушение бизнес-правил
```

### Использование

```python
try:
    service.create(data)
except ValidationError as e:
    # Показать ошибку валидации пользователю
    pass
except BusinessLogicError as e:
    # Показать ошибку бизнес-логики
    pass
except ServiceError as e:
    # Общая ошибка сервиса
    pass
```

## Система логирования

### Возможности

Новая система логирования предоставляет:

- **Ротация логов** - автоматическое создание backup файлов при превышении размера
- **Разные уровни** для разных модулей (GUI, DB, Services и т.д.)
- **Цветной вывод** в консоль для удобства разработки
- **Аудит критических операций** в отдельный файл `audit.log`
- **Декоратор производительности** для отслеживания медленных операций
- **Конфигурация** через `config.ini`

### Настройка в config.ini

```ini
[LOGGING]
level = INFO
file = app.log
max_bytes = 10485760  # 10MB
backup_count = 5
```

### Использование

```python
from utils.logger import get_logger, log_audit, log_performance

# Получение логгера для модуля
logger = get_logger('gui')
logger.info("Запуск главного окна")
logger.error("Ошибка подключения к БД")

# Аудит критических операций
log_audit(user, 'create_material', material_id, 'Создан новый материал')
log_audit(user, 'delete_user', user_id, 'Удален пользователь')

# Мониторинг производительности
@log_performance
def slow_database_operation():
    # Код операции
    pass
```

### Уровни логирования по модулям

- **GUI** - INFO (пользовательские действия)
- **DB** - DEBUG (SQL запросы)
- **Services** - INFO (бизнес-логика)
- **Repositories** - DEBUG (CRUD операции)
- **Utils** - WARNING (только важные события)

### Настройка для разработки/продакшена

```python
from utils.logger import setup_development_logging, setup_production_logging

# Для разработки (подробное логирование)
setup_development_logging()

# Для продакшена (минимальное логирование)
setup_production_logging()
```

### Обратная совместимость

Старая функция `log_event()` из `logger.py` продолжает работать, но выдает предупреждение о необходимости перехода на новую систему.

```python
# В сервисах и репозиториях
logger.info(f"Создана запись ID: {record_id}")
logger.warning(f"Запись не найдена ID: {record_id}")
logger.error(f"Ошибка БД: {error}")
```

## Постепенная миграция

### Этапы рефакторинга

1. **Создание новой структуры** ✅
2. **Создание базовых классов** ✅
3. **Настройка тестирования** ✅
4. **Создание конкретных репозиториев** (следующий этап)
5. **Создание конкретных сервисов**
6. **Рефакторинг GUI для использования сервисов**
7. **Постепенное удаление старого кода**

### Правила миграции

- ❌ Не ломать существующий функционал
- ✅ Создавать новые модули рядом со старыми
- ✅ Покрывать новый код тестами
- ✅ Использовать type hints
- ✅ Следовать PEP 8

## Конфигурация

### Новый менеджер конфигурации

```python
from utils.config import config_manager

# Получение значений
db_path = config_manager.get('DATABASE', 'path')
debug_mode = config_manager.get_bool('DEBUG', 'enabled')
max_size = config_manager.get_int('FILES', 'max_size')

# Установка значений
config_manager.set('DATABASE', 'path', '/new/path/to/db.sqlite')
config_manager.save_config()
```

## Следующие шаги

1. Создать конкретные репозитории (MaterialRepository, UserRepository и т.д.)
2. Создать конкретные сервисы (MaterialService, UserService и т.д.)
3. Обновить GUI для использования сервисов вместо прямого обращения к БД
4. Добавить интеграционные тесты
5. Настроить CI/CD для автоматического запуска тестов
6. Добавить документацию API

## Полезные команды

```bash
# Установка зависимостей для разработки
pip install -r requirements-dev.txt

# Запуск тестов
pytest

# Проверка качества кода
pylint material_control_app/
black material_control_app/
mypy material_control_app/

# Применение pre-commit хуков
pre-commit run --all-files
```

## Заключение

Новая архитектура обеспечивает:

- ✅ Разделение ответственности
- ✅ Легкость тестирования
- ✅ Масштабируемость
- ✅ Поддерживаемость
- ✅ Безопасность данных
- ✅ Соответствие современным практикам разработки
