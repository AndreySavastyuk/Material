# MaterialsRepository и MaterialsService

## Обзор

MaterialsRepository - это репозиторий для работы с материалами в системе контроля материалов. Он наследуется от BaseRepository и предоставляет специализированные методы для работы с материалами, их документами и блокировками.

MaterialsService - это сервисный слой, который обрабатывает бизнес-логику и валидацию для операций с материалами.

## Архитектура

```
GUI/API Layer
     ↓
MaterialsService (бизнес-логика, валидация)
     ↓
MaterialsRepository (доступ к данным)
     ↓
Database (SQLite)
```

## MaterialsRepository

### Инициализация

```python
from repositories.materials_repository import MaterialsRepository
import sqlite3

# Создание подключения к БД
conn = sqlite3.connect('materials.db')
conn.row_factory = sqlite3.Row

# Инициализация репозитория
docs_root = '/path/to/documents'
materials_repo = MaterialsRepository(conn, docs_root)
```

### Основные методы

#### 1. Получение материалов

```python
# Получение всех материалов с данными из связанных таблиц
materials = materials_repo.get_materials_with_relations()

# Включая помеченные на удаление
all_materials = materials_repo.get_materials_with_relations(include_deleted=True)

# Получение материала по ID
material = materials_repo.get_by_id(123)

# Поиск материалов
results = materials_repo.search_materials('ГОСТ 123')

# Материалы по поставщику
supplier_materials = materials_repo.get_materials_by_supplier(1)

# Материалы по марке
grade_materials = materials_repo.get_materials_by_grade(2)

# Материалы для лабораторных испытаний
lab_materials = materials_repo.get_materials_needing_lab_tests()
```

#### 2. Создание и обновление

```python
# Создание материала
material_data = {
    'arrival_date': '2024-01-15',
    'supplier_id': 1,
    'grade_id': 2,
    'rolling_type_id': 1,
    'size': '10x100x1000',
    'cert_num': 'CERT-2024-001',
    'cert_date': '2024-01-10',
    'batch': 'BATCH-001',
    'heat_num': 'HEAT-001',
    'volume_length_mm': 1000.0,
    'volume_weight_kg': 78.5,
    'needs_lab': 1,
    'otk_remarks': 'Качество соответствует требованиям'
}

material_id = materials_repo.create_material(material_data)

# Обновление материала
update_data = {
    'otk_remarks': 'Обновленные заметки ОТК',
    'needs_lab': 0
}
success = materials_repo.update_material(material_id, update_data)
```

#### 3. Удаление

```python
# Пометка на удаление (soft delete)
materials_repo.mark_for_deletion(material_id)

# Снятие пометки удаления
materials_repo.unmark_for_deletion(material_id)

# Получение помеченных на удаление
deleted_materials = materials_repo.get_marked_for_deletion()

# Физическое удаление (осторожно!)
materials_repo.permanently_delete_material(material_id)
```

#### 4. Блокировки

```python
# Захват блокировки
success = materials_repo.acquire_lock(material_id, 'admin')

# Проверка блокировки
is_locked, locked_by = materials_repo.is_locked(material_id)

# Освобождение блокировки
materials_repo.release_lock(material_id, 'admin')
```

#### 5. Документы

```python
# Получение документов материала
documents = materials_repo.get_documents(material_id)

# Добавление документа
document_id = materials_repo.add_document(
    material_id=material_id,
    doc_type='certificate',
    src_path='/path/to/certificate.pdf',
    uploaded_by='admin'
)
```

#### 6. Статистика

```python
# Получение статистики
stats = materials_repo.get_materials_statistics()
print(f"Всего материалов: {stats['total_materials']}")
print(f"Помечено на удаление: {stats['deleted_materials']}")
print(f"Требует лабораторных испытаний: {stats['lab_needed']}")
print(f"Заблокировано: {stats['locked_materials']}")
```

## MaterialsService

### Инициализация

```python
from services.materials_service import MaterialsService
from repositories.materials_repository import MaterialsRepository

# Создание сервиса
materials_service = MaterialsService(materials_repo)
```

### Основные методы

#### 1. Создание материала с валидацией

```python
try:
    material_data = {
        'arrival_date': '2024-01-15',
        'supplier_id': 1,
        'grade_id': 2,
        # ... другие поля
    }

    material_id = materials_service.create(material_data)
    print(f"Создан материал с ID: {material_id}")

except ValidationError as e:
    print(f"Ошибка валидации: {e}")
except RequiredFieldError as e:
    print(f"Отсутствует обязательное поле: {e}")
```

#### 2. Обновление с валидацией

```python
try:
    update_data = {'otk_remarks': 'Новые заметки'}
    success = materials_service.update(material_id, update_data)

except RecordNotFoundError as e:
    print(f"Материал не найден: {e}")
except ValidationError as e:
    print(f"Ошибка валидации: {e}")
```

#### 3. Удаление с проверками безопасности

```python
try:
    # Пометка на удаление с проверкой блокировки
    success = materials_service.mark_for_deletion(material_id, 'admin')

    # Физическое удаление с проверкой пометки
    success = materials_service.permanently_delete(material_id, 'admin')

except BusinessLogicError as e:
    print(f"Ошибка бизнес-логики: {e}")
except RecordNotFoundError as e:
    print(f"Материал не найден: {e}")
```

#### 4. Работа с блокировками

```python
# Захват блокировки
success = materials_service.acquire_material_lock(material_id, 'admin')

# Проверка статуса
is_locked, locked_by = materials_service.get_material_lock_status(material_id)

# Освобождение блокировки
materials_service.release_material_lock(material_id, 'admin')
```

#### 5. Поиск и фильтрация

```python
try:
    # Поиск с валидацией длины запроса
    results = materials_service.search_materials('ГОСТ 123')

    # Получение по критериям
    supplier_materials = materials_service.get_materials_by_supplier(1)
    grade_materials = materials_service.get_materials_by_grade(2)
    lab_materials = materials_service.get_materials_needing_lab_tests()

except ValidationError as e:
    print(f"Некорректный поисковый запрос: {e}")
```

#### 6. Документы с валидацией

```python
try:
    document_id = materials_service.add_document(
        material_id=material_id,
        doc_type='certificate',  # certificate, photo, report, drawing, other
        file_path='/path/to/file.pdf',
        uploaded_by='admin'
    )

    documents = materials_service.get_material_documents(material_id)

except ValidationError as e:
    print(f"Ошибка валидации документа: {e}")
except RecordNotFoundError as e:
    print(f"Материал не найден: {e}")
```

## Валидация данных

### Обязательные поля для создания

- `arrival_date` - дата поступления (формат: YYYY-MM-DD)
- `supplier_id` - ID поставщика (целое число > 0)
- `grade_id` - ID марки материала (целое число > 0)

### Ограничения полей

```python
# Строковые поля (максимальная длина)
'order_num': 50        # номер заказа
'size': 100           # размеры
'cert_num': 50        # номер сертификата
'batch': 50           # номер партии
'heat_num': 50        # номер плавки
'otk_remarks': 1000   # заметки ОТК

# Числовые поля (диапазоны)
'volume_length_mm': (0, 100000)    # длина в мм
'volume_weight_kg': (0, 100000)    # вес в кг
'needs_lab': (0, 1)               # требует лаб. испытаний
'supplier_id': (1, 999999)        # ID поставщика
'grade_id': (1, 999999)           # ID марки

# Даты (формат ISO: YYYY-MM-DD)
'arrival_date'  # дата поступления
'cert_date'     # дата сертификата
```

### Типы документов

- `certificate` - сертификат качества
- `photo` - фотография материала
- `report` - отчет испытаний
- `drawing` - чертеж
- `other` - прочие документы

## Обработка ошибок

### Типы исключений

```python
from utils.exceptions import (
    ValidationError,      # Ошибки валидации
    RequiredFieldError,   # Отсутствие обязательных полей
    InvalidFormatError,   # Неверный формат данных
    ValueOutOfRangeError, # Значение вне диапазона
    RecordNotFoundError,  # Запись не найдена
    BusinessLogicError,   # Нарушение бизнес-логики
    DatabaseError        # Ошибки БД
)
```

### Примеры обработки

```python
try:
    materials_service.create(material_data)
except RequiredFieldError as e:
    # Показать пользователю какие поля обязательны
    print(f"Заполните поле: {e.field_name}")
except InvalidFormatError as e:
    # Показать правильный формат
    print(f"Неверный формат поля {e.field_name}: {e.suggestions}")
except ValueOutOfRangeError as e:
    # Показать допустимый диапазон
    print(f"Значение {e.field_name} должно быть от {e.min_value} до {e.max_value}")
except DatabaseError as e:
    # Логировать и показать общую ошибку
    logger.error(f"Ошибка БД: {e}")
    print("Произошла ошибка при сохранении данных")
```

## Интеграция с Database

MaterialsRepository интегрирован в класс Database через паттерн "ленивая загрузка":

```python
# В Database классе
@property
def materials_repository(self):
    if self._materials_repository is None and self.conn:
        self._materials_repository = MaterialsRepository(self.conn, self.docs_root)
    return self._materials_repository

# Использование в существующих методах
def get_materials(self):
    if self.materials_repository:
        try:
            return self.materials_repository.get_materials_with_relations()
        except Exception as e:
            logger.error(f"Ошибка в MaterialsRepository: {e}")
            # Fallback к старому методу
    # ... старый код как fallback
```

## Примеры использования в GUI

```python
class MaterialDialog:
    def __init__(self, materials_service):
        self.materials_service = materials_service

    def save_material(self):
        try:
            data = self.collect_form_data()
            material_id = self.materials_service.create(data)
            QMessageBox.information(self, "Успех", f"Материал создан (ID: {material_id})")
        except ValidationError as e:
            QMessageBox.warning(self, "Ошибка валидации", str(e))
        except RequiredFieldError as e:
            QMessageBox.warning(self, "Заполните поле", f"Обязательное поле: {e.field_name}")
```

## Тестирование

Для тестирования используются mock-объекты:

```python
def test_create_material():
    mock_repo = Mock(spec=MaterialsRepository)
    mock_repo.create_material.return_value = 123

    service = MaterialsService(mock_repo)
    result = service.create(valid_data)

    assert result == 123
    mock_repo.create_material.assert_called_once_with(valid_data)
```

## Миграция от старого кода

1. **Постепенная миграция** - старые методы Database поддерживают fallback
2. **Обратная совместимость** - интерфейс Database остается прежним
3. **Новый код** должен использовать MaterialsService
4. **Старый код** продолжает работать через fallback механизм

## Производительность

- **Транзакции** - все изменения выполняются в транзакциях
- **Индексы** - используются индексы для быстрого поиска
- **Кэширование** - избегайте повторных запросов одних и тех же данных
- **Пакетные операции** - для множественных операций используйте транзакции

## Логирование

Все операции логируются с соответствующими уровнями:

```python
logger.info("Создан материал ID: 123")        # Успешные операции
logger.warning("Материал ID: 123 не обновлен") # Предупреждения
logger.error("Ошибка при создании материала")  # Ошибки
```
