"""
Базовый класс для всех сервисов.
Содержит общую логику валидации и обработки исключений.
"""

from typing import Dict, List, Optional, Any, Type
from abc import ABC, abstractmethod
import sqlite3
from datetime import datetime
from utils.logger import get_logger

# Импортируем исключения из новой системы
from utils.exceptions import (
    BaseApplicationError, ValidationError, RequiredFieldError,
    InvalidFormatError, ValueOutOfRangeError, DatabaseError,
    RecordNotFoundError, BusinessLogicError, DuplicateRecordError,
    IntegrityConstraintError
)

# Получаем логгер для сервисов
logger = get_logger('services')

# Для обратной совместимости
ServiceError = BaseApplicationError
NotFoundError = RecordNotFoundError


class BaseService(ABC):
    """
    Базовый класс для всех сервисов.
    Содержит общую логику валидации и обработки ошибок.
    """
    
    def __init__(self, repository):
        """
        Инициализация сервиса.
        
        Args:
            repository: Репозиторий для работы с данными
        """
        self._repository = repository
        self._logger = get_logger('services')
    
    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Валидация обязательных полей.
        
        Args:
            data: Данные для валидации
            required_fields: Список обязательных полей
            
        Raises:
            RequiredFieldError: Если обязательное поле отсутствует
        """
        missing_fields = []
        
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                missing_fields.append(field)
        
        if missing_fields:
            if len(missing_fields) == 1:
                raise RequiredFieldError(
                    f"Отсутствует обязательное поле: {missing_fields[0]}",
                    field_name=missing_fields[0]
                )
            else:
                raise ValidationError(
                    f"Отсутствуют обязательные поля: {', '.join(missing_fields)}",
                    details={'missing_fields': missing_fields},
                    suggestions=[f"Заполните поля: {', '.join(missing_fields)}"]
                )
    
    def validate_data_types(self, data: Dict[str, Any], field_types: Dict[str, Type]) -> None:
        """
        Валидация типов данных.
        
        Args:
            data: Данные для валидации
            field_types: Словарь с ожидаемыми типами полей
            
        Raises:
            InvalidFormatError: Если тип данных не соответствует ожидаемому
        """
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    raise InvalidFormatError(
                        f"Поле '{field}' должно быть типа {expected_type.__name__}, "
                        f"получено {type(data[field]).__name__}",
                        field_name=field,
                        field_value=data[field],
                        suggestions=[
                            f"Убедитесь, что значение имеет тип {expected_type.__name__}",
                            "Проверьте правильность ввода данных"
                        ]
                    )
    
    def validate_string_length(self, data: Dict[str, Any], field_limits: Dict[str, int]) -> None:
        """
        Валидация длины строковых полей.
        
        Args:
            data: Данные для валидации
            field_limits: Словарь с максимальными длинами полей
            
        Raises:
            ValueOutOfRangeError: Если длина строки превышает лимит
        """
        for field, max_length in field_limits.items():
            if field in data and data[field] is not None:
                if isinstance(data[field], str) and len(data[field]) > max_length:
                    raise ValueOutOfRangeError(
                        f"Поле '{field}' не может быть длиннее {max_length} символов",
                        field_name=field,
                        field_value=data[field],
                        min_value=0,
                        max_value=max_length,
                        suggestions=[
                            f"Сократите текст до {max_length} символов",
                            "Используйте более краткую формулировку"
                        ]
                    )
    
    def validate_numeric_range(self, data: Dict[str, Any], field_ranges: Dict[str, tuple]) -> None:
        """
        Валидация диапазона числовых полей.
        
        Args:
            data: Данные для валидации
            field_ranges: Словарь с диапазонами (min, max) для полей
            
        Raises:
            ValueOutOfRangeError: Если значение вне диапазона
        """
        for field, (min_val, max_val) in field_ranges.items():
            if field in data and data[field] is not None:
                value = data[field]
                if isinstance(value, (int, float)):
                    if value < min_val or value > max_val:
                        raise ValueOutOfRangeError(
                            f"Поле '{field}' должно быть в диапазоне от {min_val} до {max_val}",
                            field_name=field,
                            field_value=value,
                            min_value=min_val,
                            max_value=max_val,
                            suggestions=[
                                f"Введите значение между {min_val} и {max_val}",
                                "Проверьте правильность введенных данных"
                            ]
                        )
    
    def validate_date_format(self, data: Dict[str, Any], date_fields: List[str]) -> None:
        """
        Валидация формата даты (ISO: YYYY-MM-DD).
        
        Args:
            data: Данные для валидации
            date_fields: Список полей с датами
            
        Raises:
            InvalidFormatError: Если формат даты неверный
        """
        for field in date_fields:
            if field in data and data[field] is not None:
                try:
                    datetime.strptime(data[field], '%Y-%m-%d')
                except ValueError:
                    raise InvalidFormatError(
                        f"Поле '{field}' должно быть в формате YYYY-MM-DD",
                        field_name=field,
                        field_value=data[field],
                        suggestions=[
                            "Используйте формат даты YYYY-MM-DD (например: 2023-12-31)",
                            "Проверьте правильность введенной даты"
                        ]
                    )
    
    def handle_db_error(self, error: Exception, operation: str) -> None:
        """
        Обработка ошибок базы данных.
        
        Args:
            error: Исключение
            operation: Описание операции
            
        Raises:
            DatabaseError: Обработанное исключение
        """
        self._logger.error(f"Ошибка БД при {operation}: {error}")
        
        if isinstance(error, sqlite3.IntegrityError):
            if "UNIQUE constraint failed" in str(error):
                raise DuplicateRecordError(
                    f"Запись с такими данными уже существует при {operation}",
                    original_error=error,
                    suggestions=[
                        "Проверьте уникальность данных",
                        "Используйте другие значения для уникальных полей"
                    ]
                )
            elif "FOREIGN KEY constraint failed" in str(error):
                raise IntegrityConstraintError(
                    f"Нарушена связь с другой таблицей при {operation}",
                    original_error=error,
                    suggestions=[
                        "Проверьте существование связанных записей",
                        "Убедитесь, что связанные записи не удалены"
                    ]
                )
            else:
                raise IntegrityConstraintError(
                    f"Нарушение целостности данных при {operation}",
                    original_error=error,
                    suggestions=[
                        "Проверьте корректность данных",
                        "Убедитесь в соответствии данных ограничениям БД"
                    ]
                )
        elif isinstance(error, sqlite3.OperationalError):
            raise DatabaseError(
                f"Ошибка выполнения операции с базой данных при {operation}",
                original_error=error,
                suggestions=[
                    "Проверьте доступность базы данных",
                    "Убедитесь в корректности SQL запроса"
                ]
            )
        else:
            raise DatabaseError(
                f"Неизвестная ошибка базы данных при {operation}: {error}",
                original_error=error,
                suggestions=[
                    "Обратитесь к администратору системы",
                    "Проверьте логи для получения подробной информации"
                ]
            )
    
    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение записи по ID.
        
        Args:
            record_id: ID записи
            
        Returns:
            Словарь с данными записи или None
            
        Raises:
            ServiceError: Ошибка при получении записи
        """
        try:
            self._logger.info(f"Получение записи ID: {record_id}")
            return self._repository.get_by_id(record_id)
            
        except Exception as e:
            self.handle_db_error(e, f"получении записи ID: {record_id}")
    
    def get_all(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Получение всех записей.
        
        Args:
            filters: Фильтры для запроса
            
        Returns:
            Список словарей с данными записей
            
        Raises:
            ServiceError: Ошибка при получении записей
        """
        try:
            self._logger.info("Получение всех записей")
            return self._repository.get_all(filters)
            
        except Exception as e:
            self.handle_db_error(e, "получении всех записей")
    
    def delete_by_id(self, record_id: int) -> bool:
        """
        Удаление записи по ID.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись удалена
            
        Raises:
            NotFoundError: Если запись не найдена
            ServiceError: Ошибка при удалении
        """
        try:
            self._logger.info(f"Удаление записи ID: {record_id}")
            
            # Проверяем существование записи
            if not self._repository.exists(record_id):
                raise NotFoundError(f"Запись с ID {record_id} не найдена")
            
            return self._repository.delete(record_id)
            
        except NotFoundError:
            raise
        except Exception as e:
            self.handle_db_error(e, f"удалении записи ID: {record_id}")
    
    def soft_delete_by_id(self, record_id: int) -> bool:
        """
        Мягкое удаление записи по ID.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись помечена на удаление
            
        Raises:
            NotFoundError: Если запись не найдена
            ServiceError: Ошибка при удалении
        """
        try:
            self._logger.info(f"Мягкое удаление записи ID: {record_id}")
            
            # Проверяем существование записи
            if not self._repository.exists(record_id):
                raise NotFoundError(f"Запись с ID {record_id} не найдена")
            
            return self._repository.soft_delete(record_id)
            
        except NotFoundError:
            raise
        except Exception as e:
            self.handle_db_error(e, f"мягком удалении записи ID: {record_id}")
    
    def restore_by_id(self, record_id: int) -> bool:
        """
        Восстановление мягко удаленной записи.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись восстановлена
            
        Raises:
            NotFoundError: Если запись не найдена
            ServiceError: Ошибка при восстановлении
        """
        try:
            self._logger.info(f"Восстановление записи ID: {record_id}")
            
            # Проверяем существование записи
            if not self._repository.exists(record_id):
                raise NotFoundError(f"Запись с ID {record_id} не найдена")
            
            return self._repository.restore(record_id)
            
        except NotFoundError:
            raise
        except Exception as e:
            self.handle_db_error(e, f"восстановлении записи ID: {record_id}")
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Подсчет количества записей.
        
        Args:
            filters: Фильтры для запроса
            
        Returns:
            Количество записей
            
        Raises:
            ServiceError: Ошибка при подсчете
        """
        try:
            self._logger.info("Подсчет количества записей")
            return self._repository.count(filters)
            
        except Exception as e:
            self.handle_db_error(e, "подсчете количества записей")
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> int:
        """
        Создание новой записи.
        Должен быть переопределен в наследниках.
        
        Args:
            data: Данные для создания записи
            
        Returns:
            ID созданной записи
        """
        pass
    
    @abstractmethod
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """
        Обновление записи.
        Должен быть переопределен в наследниках.
        
        Args:
            record_id: ID записи
            data: Данные для обновления
            
        Returns:
            True если запись обновлена
        """
        pass 