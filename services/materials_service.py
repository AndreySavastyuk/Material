"""
Сервис для работы с материалами.
Содержит бизнес-логику и валидацию для операций с материалами.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import os
import math
import re
from functools import lru_cache

from services.base import BaseService
from repositories.materials_repository import MaterialsRepository
from utils.exceptions import (
    ValidationError, RequiredFieldError, InvalidFormatError,
    ValueOutOfRangeError, RecordNotFoundError, BusinessLogicError
)
from utils.logger import get_logger

logger = get_logger('services.materials')


class MaterialsService(BaseService):
    """
    Сервис для работы с материалами.
    Обрабатывает бизнес-логику, валидацию и координирует работу с репозиторием.
    """
    
    def __init__(self, materials_repository: MaterialsRepository):
        """
        Инициализация сервиса материалов.
        
        Args:
            materials_repository: Репозиторий для работы с материалами
        """
        super().__init__(materials_repository)
        self._materials_repo = materials_repository
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Создает новый материал с валидацией.
        
        Args:
            data: Данные материала
            
        Returns:
            ID созданного материала
            
        Raises:
            ValidationError: При ошибке валидации
            DatabaseError: При ошибке БД
        """
        try:
            # Валидация обязательных полей
            required_fields = ['arrival_date', 'supplier_id', 'grade_id']
            self.validate_required_fields(data, required_fields)
            
            # Валидация типов данных
            field_types = {
                'supplier_id': int,
                'grade_id': int,
                'rolling_type_id': int,
                'volume_length_mm': (int, float),
                'volume_weight_kg': (int, float),
                'needs_lab': int
            }
            self._validate_flexible_types(data, field_types)
            
            # Валидация длины строк
            string_limits = {
                'order_num': 50,
                'size': 100,
                'cert_num': 50,
                'batch': 50,
                'heat_num': 50,
                'otk_remarks': 1000
            }
            self.validate_string_length(data, string_limits)
            
            # Валидация дат
            date_fields = ['arrival_date', 'cert_date']
            self.validate_date_format(data, date_fields)
            
            # Валидация числовых диапазонов
            numeric_ranges = {
                'volume_length_mm': (0, 100000),  # до 100 метров
                'volume_weight_kg': (0, 100000),   # до 100 тонн
                'needs_lab': (0, 1),
                'supplier_id': (1, 999999),
                'grade_id': (1, 999999)
            }
            self.validate_numeric_range(data, numeric_ranges)
            
            # Создание материала
            material_id = self._materials_repo.create_material(data)
            
            logger.info(f"Создан материал ID: {material_id}")
            return material_id
            
        except (ValidationError, RequiredFieldError, InvalidFormatError, ValueOutOfRangeError):
            # Пробрасываем ошибки валидации как есть
            raise
        except Exception as e:
            self.handle_db_error(e, "создании материала")
            raise
    
    def update(self, material_id: int, data: Dict[str, Any]) -> bool:
        """
        Обновляет материал с валидацией.
        
        Args:
            material_id: ID материала
            data: Данные для обновления
            
        Returns:
            True если обновлен, False если не найден
            
        Raises:
            ValidationError: При ошибке валидации
            RecordNotFoundError: Если материал не найден
        """
        try:
            # Проверяем существование материала
            if not self._materials_repo.exists(material_id):
                raise RecordNotFoundError(
                    f"Материал с ID {material_id} не найден",
                    suggestions=["Проверьте правильность ID материала"]
                )
            
            # Валидация обновляемых данных (без обязательных полей)
            field_types = {
                'supplier_id': int,
                'grade_id': int,
                'rolling_type_id': int,
                'volume_length_mm': (int, float),
                'volume_weight_kg': (int, float),
                'needs_lab': int
            }
            self._validate_flexible_types(data, field_types)
            
            # Валидация длины строк
            string_limits = {
                'order_num': 50,
                'size': 100,
                'cert_num': 50,
                'batch': 50,
                'heat_num': 50,
                'otk_remarks': 1000
            }
            self.validate_string_length(data, string_limits)
            
            # Валидация дат
            date_fields = ['arrival_date', 'cert_date']
            self.validate_date_format(data, date_fields)
            
            # Валидация числовых диапазонов
            numeric_ranges = {
                'volume_length_mm': (0, 100000),
                'volume_weight_kg': (0, 100000),
                'needs_lab': (0, 1),
                'supplier_id': (1, 999999),
                'grade_id': (1, 999999)
            }
            self.validate_numeric_range(data, numeric_ranges)
            
            # Обновление материала
            success = self._materials_repo.update_material(material_id, data)
            
            if success:
                logger.info(f"Обновлен материал ID: {material_id}")
            else:
                logger.warning(f"Материал ID: {material_id} не обновлен")
                
            return success
            
        except (ValidationError, RecordNotFoundError, InvalidFormatError, ValueOutOfRangeError):
            # Пробрасываем бизнес-ошибки как есть
            raise
        except Exception as e:
            self.handle_db_error(e, f"обновлении материала {material_id}")
            raise
    
    def get_all_materials(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Получает все материалы с данными из связанных таблиц.
        
        Args:
            include_deleted: Включать помеченные на удаление
            
        Returns:
            Список материалов
        """
        try:
            materials = self._materials_repo.get_materials_with_relations(include_deleted)
            logger.info(f"Получено {len(materials)} материалов")
            return materials
            
        except Exception as e:
            self.handle_db_error(e, "получении материалов")
            raise
    
    def get_material_by_id(self, material_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает материал по ID.
        
        Args:
            material_id: ID материала
            
        Returns:
            Данные материала или None
        """
        try:
            material = self._materials_repo.get_by_id(material_id)
            if material:
                logger.info(f"Получен материал ID: {material_id}")
            else:
                logger.warning(f"Материал ID: {material_id} не найден")
            return material
            
        except Exception as e:
            self.handle_db_error(e, f"получении материала {material_id}")
            raise
    
    def mark_for_deletion(self, material_id: int, user_login: str) -> bool:
        """
        Помечает материал на удаление с бизнес-логикой.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если помечен
            
        Raises:
            RecordNotFoundError: Если материал не найден
            BusinessLogicError: Если материал заблокирован другим пользователем
        """
        try:
            # Проверяем существование материала
            if not self._materials_repo.exists(material_id):
                raise RecordNotFoundError(
                    f"Материал с ID {material_id} не найден",
                    suggestions=["Проверьте правильность ID материала"]
                )
            
            # Проверяем блокировку
            is_locked, locked_by = self._materials_repo.is_locked(material_id)
            if is_locked and locked_by != user_login:
                raise BusinessLogicError(
                    f"Материал заблокирован пользователем {locked_by}",
                    suggestions=[
                        f"Дождитесь освобождения блокировки пользователем {locked_by}",
                        "Обратитесь к администратору"
                    ]
                )
            
            # Помечаем на удаление
            success = self._materials_repo.mark_for_deletion(material_id)
            
            if success:
                logger.info(f"Материал {material_id} помечен на удаление пользователем {user_login}")
            
            return success
            
        except (RecordNotFoundError, BusinessLogicError):
            # Пробрасываем бизнес-ошибки как есть
            raise
        except Exception as e:
            self.handle_db_error(e, f"пометке материала {material_id} на удаление")
            raise
    
    def unmark_for_deletion(self, material_id: int, user_login: str) -> bool:
        """
        Снимает пометку удаления с материала.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если пометка снята
        """
        try:
            # Проверяем существование материала
            if not self._materials_repo.exists(material_id):
                raise RecordNotFoundError(
                    f"Материал с ID {material_id} не найден",
                    suggestions=["Проверьте правильность ID материала"]
                )
            
            # Снимаем пометку
            success = self._materials_repo.unmark_for_deletion(material_id)
            
            if success:
                logger.info(f"С материала {material_id} снята пометка удаления пользователем {user_login}")
            
            return success
            
        except Exception as e:
            self.handle_db_error(e, f"снятии пометки удаления с материала {material_id}")
            raise
    
    def permanently_delete(self, material_id: int, user_login: str) -> bool:
        """
        Физически удаляет материал с проверками безопасности.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если удален
            
        Raises:
            BusinessLogicError: Если материал не помечен на удаление
        """
        try:
            # Проверяем, что материал помечен на удаление
            material = self._materials_repo.get_by_id(material_id)
            if not material:
                raise RecordNotFoundError(
                    f"Материал с ID {material_id} не найден",
                    suggestions=["Проверьте правильность ID материала"]
                )
            
            if not material.get('to_delete', 0):
                raise BusinessLogicError(
                    "Материал должен быть сначала помечен на удаление",
                    suggestions=["Сначала пометьте материал на удаление"]
                )
            
            # Физически удаляем
            success = self._materials_repo.permanently_delete_material(material_id)
            
            if success:
                logger.warning(f"Материал {material_id} физически удален пользователем {user_login}")
            
            return success
            
        except (RecordNotFoundError, BusinessLogicError):
            # Пробрасываем бизнес-ошибки как есть
            raise
        except Exception as e:
            self.handle_db_error(e, f"физическом удалении материала {material_id}")
            raise
    
    def acquire_material_lock(self, material_id: int, user_login: str) -> bool:
        """
        Захватывает блокировку на материал.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если блокировка захвачена
        """
        try:
            success = self._materials_repo.acquire_lock(material_id, user_login)
            
            if success:
                logger.info(f"Материал {material_id} заблокирован пользователем {user_login}")
            else:
                logger.warning(f"Не удалось заблокировать материал {material_id} пользователем {user_login}")
            
            return success
            
        except Exception as e:
            self.handle_db_error(e, f"захвате блокировки материала {material_id}")
            raise
    
    def release_material_lock(self, material_id: int, user_login: str) -> bool:
        """
        Освобождает блокировку материала.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если блокировка освобождена
        """
        try:
            success = self._materials_repo.release_lock(material_id, user_login)
            
            if success:
                logger.info(f"Блокировка материала {material_id} освобождена пользователем {user_login}")
            
            return success
            
        except Exception as e:
            self.handle_db_error(e, f"освобождении блокировки материала {material_id}")
            raise
    
    def get_material_lock_status(self, material_id: int) -> Tuple[bool, str]:
        """
        Получает статус блокировки материала.
        
        Args:
            material_id: ID материала
            
        Returns:
            Кортеж (заблокирован, логин_пользователя)
        """
        try:
            return self._materials_repo.is_locked(material_id)
            
        except Exception as e:
            self.handle_db_error(e, f"проверке блокировки материала {material_id}")
            raise
    
    def search_materials(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Поиск материалов по различным полям.
        
        Args:
            search_term: Поисковый запрос
            
        Returns:
            Список найденных материалов
            
        Raises:
            ValidationError: Если поисковый запрос слишком короткий
        """
        try:
            if len(search_term.strip()) < 2:
                raise ValidationError(
                    "Поисковый запрос должен содержать минимум 2 символа",
                    suggestions=["Введите больше символов для поиска"]
                )
            
            materials = self._materials_repo.search_materials(search_term.strip())
            logger.info(f"Найдено {len(materials)} материалов по запросу: {search_term}")
            return materials
            
        except ValidationError:
            # Пробрасываем ошибки валидации как есть
            raise
        except Exception as e:
            self.handle_db_error(e, f"поиске материалов по запросу: {search_term}")
            raise
    
    def get_materials_by_supplier(self, supplier_id: int) -> List[Dict[str, Any]]:
        """
        Получает материалы определенного поставщика.
        
        Args:
            supplier_id: ID поставщика
            
        Returns:
            Список материалов поставщика
        """
        try:
            materials = self._materials_repo.get_materials_by_supplier(supplier_id)
            logger.info(f"Получено {len(materials)} материалов поставщика {supplier_id}")
            return materials
            
        except Exception as e:
            self.handle_db_error(e, f"получении материалов поставщика {supplier_id}")
            raise
    
    def get_materials_by_grade(self, grade_id: int) -> List[Dict[str, Any]]:
        """
        Получает материалы определенной марки.
        
        Args:
            grade_id: ID марки
            
        Returns:
            Список материалов марки
        """
        try:
            materials = self._materials_repo.get_materials_by_grade(grade_id)
            logger.info(f"Получено {len(materials)} материалов марки {grade_id}")
            return materials
            
        except Exception as e:
            self.handle_db_error(e, f"получении материалов марки {grade_id}")
            raise
    
    def get_materials_needing_lab_tests(self) -> List[Dict[str, Any]]:
        """
        Получает материалы, требующие лабораторных испытаний.
        
        Returns:
            Список материалов для лабораторных испытаний
        """
        try:
            materials = self._materials_repo.get_materials_needing_lab_tests()
            logger.info(f"Получено {len(materials)} материалов для лабораторных испытаний")
            return materials
            
        except Exception as e:
            self.handle_db_error(e, "получении материалов для лабораторных испытаний")
            raise
    
    def get_materials_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по материалам.
        
        Returns:
            Словарь со статистикой
        """
        try:
            stats = self._materials_repo.get_materials_statistics()
            logger.info("Получена статистика по материалам")
            return stats
            
        except Exception as e:
            self.handle_db_error(e, "получении статистики материалов")
            raise
    
    def add_document(self, material_id: int, doc_type: str, file_path: str, 
                    uploaded_by: str) -> int:
        """
        Добавляет документ к материалу с валидацией.
        
        Args:
            material_id: ID материала
            doc_type: Тип документа
            file_path: Путь к файлу
            uploaded_by: Кто загрузил
            
        Returns:
            ID созданного документа
            
        Raises:
            ValidationError: При ошибке валидации
            RecordNotFoundError: Если материал не найден
        """
        try:
            # Проверяем существование материала
            if not self._materials_repo.exists(material_id):
                raise RecordNotFoundError(
                    f"Материал с ID {material_id} не найден",
                    suggestions=["Проверьте правильность ID материала"]
                )
            
            # Проверяем существование файла
            if not os.path.exists(file_path):
                raise ValidationError(
                    f"Файл не найден: {file_path}",
                    suggestions=["Проверьте правильность пути к файлу"]
                )
            
            # Валидация типа документа
            valid_doc_types = ['certificate', 'photo', 'report', 'drawing', 'other']
            if doc_type not in valid_doc_types:
                raise ValidationError(
                    f"Недопустимый тип документа: {doc_type}",
                    suggestions=[f"Используйте один из типов: {', '.join(valid_doc_types)}"]
                )
            
            # Добавляем документ
            document_id = self._materials_repo.add_document(
                material_id, doc_type, file_path, uploaded_by
            )
            
            logger.info(f"Добавлен документ {document_id} к материалу {material_id}")
            return document_id
            
        except (ValidationError, RecordNotFoundError):
            # Пробрасываем бизнес-ошибки как есть
            raise
        except Exception as e:
            self.handle_db_error(e, f"добавлении документа к материалу {material_id}")
            raise
    
    def get_material_documents(self, material_id: int) -> List[Dict[str, Any]]:
        """
        Получает документы материала.
        
        Args:
            material_id: ID материала
            
        Returns:
            Список документов
        """
        try:
            documents = self._materials_repo.get_documents(material_id)
            logger.info(f"Получено {len(documents)} документов для материала {material_id}")
            return documents
            
        except Exception as e:
            self.handle_db_error(e, f"получении документов материала {material_id}")
            raise
    
    def _validate_flexible_types(self, data: Dict[str, Any], field_types: Dict[str, Any]) -> None:
        """
        Валидация типов данных с поддержкой множественных типов.
        
        Args:
            data: Данные для валидации
            field_types: Словарь с ожидаемыми типами полей
        """
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if isinstance(expected_type, tuple):
                    # Множественные типы
                    if not isinstance(data[field], expected_type):
                        type_names = [t.__name__ for t in expected_type]
                        raise InvalidFormatError(
                            f"Поле '{field}' должно быть типа {' или '.join(type_names)}, "
                            f"получено {type(data[field]).__name__}",
                            field_name=field,
                            field_value=data[field]
                        )
                else:
                    # Одиночный тип
                    if not isinstance(data[field], expected_type):
                        raise InvalidFormatError(
                            f"Поле '{field}' должно быть типа {expected_type.__name__}, "
                            f"получено {type(data[field]).__name__}",
                            field_name=field,
                            field_value=data[field]
                        )
    
    # === Методы для работы со справочниками (с кешированием) ===
    
    @lru_cache(maxsize=1)
    def get_suppliers(self) -> List[Dict[str, Any]]:
        """
        Получает список поставщиков с кешированием.
        
        Returns:
            Список поставщиков [{'id': int, 'name': str}]
        """
        try:
            query = "SELECT id, name FROM Suppliers ORDER BY name"
            result = self._materials_repo.execute_query(query)
            suppliers = [{'id': row[0], 'name': row[1]} for row in result]
            
            logger.info(f"Получено {len(suppliers)} поставщиков")
            return suppliers
            
        except Exception as e:
            self.handle_db_error(e, "получении поставщиков")
            raise
    
    @lru_cache(maxsize=1)
    def get_grades(self) -> List[Dict[str, Any]]:
        """
        Получает список марок с плотностью и кешированием.
        
        Returns:
            Список марок [{'id': int, 'grade': str, 'density': float}]
        """
        try:
            query = "SELECT id, grade, density FROM Grades ORDER BY grade"
            result = self._materials_repo.execute_query(query)
            grades = [{'id': row[0], 'grade': row[1], 'density': row[2]} for row in result]
            
            logger.info(f"Получено {len(grades)} марок")
            return grades
            
        except Exception as e:
            self.handle_db_error(e, "получении марок")
            raise
    
    @lru_cache(maxsize=1)
    def get_rolling_types(self) -> List[Dict[str, Any]]:
        """
        Получает список видов проката с кешированием.
        
        Returns:
            Список видов проката [{'id': int, 'name': str}]
        """
        try:
            # Проверяем структуру таблицы
            info_query = "PRAGMA table_info(RollingTypes)"
            table_info = self._materials_repo.execute_query(info_query)
            
            # Определяем правильное имя столбца
            col_name = "name"
            if len(table_info) > 1:
                col_name = table_info[1][1]  # Второй столбец
            elif table_info:
                col_name = table_info[0][1]  # Первый столбец если только один
            
            query = f"SELECT id, {col_name} FROM RollingTypes ORDER BY {col_name}"
            result = self._materials_repo.execute_query(query)
            rolling_types = [{'id': row[0], 'name': row[1]} for row in result]
            
            logger.info(f"Получено {len(rolling_types)} видов проката")
            return rolling_types
            
        except Exception as e:
            self.handle_db_error(e, "получении видов проката")
            raise
    
    @lru_cache(maxsize=1)
    def get_custom_orders(self) -> List[Dict[str, Any]]:
        """
        Получает список пользовательских заказов с кешированием.
        
        Returns:
            Список заказов [{'id': int, 'name': str}]
        """
        try:
            query = "SELECT id, name FROM CustomOrders ORDER BY name"
            result = self._materials_repo.execute_query(query)
            custom_orders = [{'id': row[0], 'name': row[1]} for row in result]
            
            logger.info(f"Получено {len(custom_orders)} пользовательских заказов")
            return custom_orders
            
        except Exception as e:
            # Если таблица не существует, возвращаем пустой список
            if "no such table" in str(e).lower():
                logger.warning("Таблица CustomOrders не найдена")
                return []
            self.handle_db_error(e, "получении пользовательских заказов")
            raise
    
    def clear_cache(self) -> None:
        """
        Очищает кеш справочников.
        Вызывается после изменений в справочниках.
        """
        self.get_suppliers.cache_clear()
        self.get_grades.cache_clear()
        self.get_rolling_types.cache_clear()
        self.get_custom_orders.cache_clear()
        logger.info("Кеш справочников очищен")
    
    # === Методы для расчета веса и объема ===
    
    def calculate_cross_section_area(self, rolling_type: str, dim1: float, dim2: float = 0) -> float:
        """
        Вычисляет площадь поперечного сечения для разных типов проката.
        
        Args:
            rolling_type: Тип проката (Круг, Лист, Труба и т.д.)
            dim1: Первый размер в мм
            dim2: Второй размер в мм (для листов, труб)
            
        Returns:
            Площадь поперечного сечения в м²
            
        Raises:
            ValidationError: При неверных параметрах
        """
        try:
            # Переводим в метры
            a1 = dim1 / 1000
            a2 = dim2 / 1000
            
            area = 0.0
            
            if rolling_type in ("Круг", "Поковка"):
                # Площадь круга: π * r²
                area = math.pi * (a1 / 2) ** 2
                
            elif rolling_type == "Шестигранник":
                # Площадь правильного шестиугольника: 3√3/2 * a²
                area = 3 * math.sqrt(3) / 2 * (a1 ** 2)
                
            elif rolling_type == "Квадрат":
                # Площадь квадрата: a²
                area = a1 ** 2
                
            elif rolling_type in ("Лист", "Плита"):
                # Площадь прямоугольника: толщина * ширина
                area = a1 * a2
                
            elif rolling_type == "Труба":
                # Площадь кольца: π * (R² - r²)
                outer_radius = a1 / 2
                wall_thickness = a2
                inner_radius = outer_radius - wall_thickness
                area = math.pi * (outer_radius ** 2 - inner_radius ** 2)
                
            else:
                raise ValidationError(
                    f"Неизвестный тип проката: {rolling_type}",
                    suggestions=[
                        "Используйте один из типов: Круг, Лист, Труба, Шестигранник, Квадрат, Плита, Поковка"
                    ]
                )
            
            logger.debug(f"Площадь сечения {rolling_type} {dim1}×{dim2}: {area:.6f} м²")
            return area
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(
                f"Ошибка расчета площади сечения: {str(e)}",
                suggestions=["Проверьте правильность размеров и типа проката"]
            )
    
    def calculate_material_weight(self, grade_id: int, rolling_type: str, 
                                 dimensions: Tuple[float, float], 
                                 volume_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Вычисляет вес материала на основе марки, типа проката и объема.
        
        Args:
            grade_id: ID марки материала
            rolling_type: Тип проката
            dimensions: Размеры (dim1, dim2) в мм
            volume_data: Список объемов [{'length': int, 'count': int}]
            
        Returns:
            Кортеж (общая длина в мм, общий вес в кг)
            
        Raises:
            ValidationError: При ошибках валидации
            RecordNotFoundError: Если марка не найдена
        """
        try:
            # Получаем плотность материала
            grades = self.get_grades()
            grade = next((g for g in grades if g['id'] == grade_id), None)
            
            if not grade:
                raise RecordNotFoundError(
                    f"Марка с ID {grade_id} не найдена",
                    suggestions=["Проверьте правильность ID марки"]
                )
            
            density = grade['density']
            dim1, dim2 = dimensions
            
            # Вычисляем площадь поперечного сечения
            area = self.calculate_cross_section_area(rolling_type, dim1, dim2)
            
            # Вычисляем общую длину
            total_length_mm = sum(item['length'] * item['count'] for item in volume_data)
            total_length_m = total_length_mm / 1000
            
            # Вычисляем вес: площадь * длина * плотность
            weight_kg = area * total_length_m * density
            
            result = (int(round(total_length_mm)), int(round(weight_kg)))
            
            logger.info(f"Расчет веса: {total_length_mm} мм, {weight_kg:.2f} кг")
            return result
            
        except (ValidationError, RecordNotFoundError):
            raise
        except Exception as e:
            raise ValidationError(
                f"Ошибка расчета веса материала: {str(e)}",
                suggestions=["Проверьте правильность данных для расчета"]
            )
    
    def process_volume_data(self, volume_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Обрабатывает данные объема и возвращает информацию для отображения.
        
        Args:
            volume_data: Список объемов [{'length': int, 'count': int}]
            
        Returns:
            Словарь с информацией об объеме
        """
        try:
            total_mm = sum(item['length'] * item['count'] for item in volume_data)
            total_m = total_mm / 1000
            
            result = {
                'total_length_mm': total_mm,
                'total_length_m': total_m,
                'display_text': f"{total_mm:.0f} мм ({total_m:.2f} м)",
                'info_text': f"Общая длина: {total_m:.2f} м",
                'pieces_count': len(volume_data),
                'total_pieces': sum(item['count'] for item in volume_data)
            }
            
            logger.debug(f"Обработка объема: {result}")
            return result
            
        except Exception as e:
            raise ValidationError(
                f"Ошибка обработки данных объема: {str(e)}",
                suggestions=["Проверьте правильность данных объема"]
            )
    
    # === Методы валидации ===
    
    def validate_order_number(self, order_number: str) -> bool:
        """
        Валидирует номер заказа в формате 9999/999.
        
        Args:
            order_number: Номер заказа
            
        Returns:
            True если формат корректный
            
        Raises:
            ValidationError: При неверном формате
        """
        try:
            # Регулярное выражение для формата 9999/999
            pattern = r'^\d{1,4}/\d{1,3}$'
            
            if not re.match(pattern, order_number):
                raise ValidationError(
                    f"Неверный формат номера заказа: {order_number}",
                    suggestions=[
                        "Используйте формат: 9999/999 (например: 2025/003)",
                        "Номер заказа должен содержать только цифры и слеш"
                    ]
                )
            
            return True
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(
                f"Ошибка валидации номера заказа: {str(e)}",
                suggestions=["Проверьте правильность номера заказа"]
            )
    
    def format_order_number(self, input_text: str) -> str:
        """
        Форматирует номер заказа в процессе ввода.
        
        Args:
            input_text: Исходный текст
            
        Returns:
            Отформатированный номер заказа
        """
        try:
            # Оставляем только цифры, максимум 7
            digits = ''.join(ch for ch in input_text if ch.isdigit())[:7]
            
            # Форматируем: первые 4 цифры, затем слеш и оставшиеся
            formatted = digits[:4]
            if len(digits) > 4:
                formatted += '/' + digits[4:]
                
            return formatted
            
        except Exception as e:
            logger.warning(f"Ошибка форматирования номера заказа: {e}")
            return input_text
    
    def validate_material_form_data(self, data: Dict[str, Any]) -> None:
        """
        Валидирует данные формы материала.
        
        Args:
            data: Данные формы
            
        Raises:
            ValidationError: При ошибках валидации
        """
        try:
            # Проверяем обязательные поля
            if not data.get('supplier_id'):
                raise ValidationError(
                    "Необходимо выбрать поставщика",
                    suggestions=["Выберите поставщика из списка"]
                )
            
            # Проверяем номер заказа если он не пользовательский
            if not data.get('is_custom_order', False):
                order_num = data.get('order_num', '')
                if order_num:
                    self.validate_order_number(order_num)
                    
            # Проверяем размеры в зависимости от типа проката
            rolling_type = data.get('rolling_type', '')
            dim1 = data.get('dim1', 0)
            dim2 = data.get('dim2', 0)
            
            if rolling_type in ("Круг", "Поковка", "Шестигранник", "Квадрат"):
                if not dim1 or dim1 <= 0:
                    raise ValidationError(
                        f"Для типа '{rolling_type}' необходимо указать размер",
                        suggestions=["Введите положительное значение размера"]
                    )
                    
            elif rolling_type in ("Лист", "Плита", "Труба"):
                if not dim1 or dim1 <= 0 or not dim2 or dim2 <= 0:
                    raise ValidationError(
                        f"Для типа '{rolling_type}' необходимо указать оба размера",
                        suggestions=["Введите положительные значения обоих размеров"]
                    )
                    
            logger.debug("Валидация данных формы пройдена")
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(
                f"Ошибка валидации данных формы: {str(e)}",
                suggestions=["Проверьте правильность заполнения формы"]
            )
    
    # === Методы для работы с форматированием данных ===
    
    def format_materials_for_display(self, materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Форматирует данные материалов для отображения в таблице.
        
        Args:
            materials: Список материалов
            
        Returns:
            Отформатированный список материалов
        """
        try:
            formatted_materials = []
            
            for material in materials:
                # Форматируем даты
                arrival_date = material.get('arrival_date', '')
                cert_date = material.get('cert_date', '')
                
                try:
                    if arrival_date:
                        arrival_dt = datetime.strptime(arrival_date, '%Y-%m-%d')
                        arrival_date = arrival_dt.strftime('%d.%m.%Y')
                except ValueError:
                    pass
                    
                try:
                    if cert_date:
                        cert_dt = datetime.strptime(cert_date, '%Y-%m-%d')
                        cert_date = cert_dt.strftime('%d.%m.%Y')
                except ValueError:
                    pass
                
                # Форматируем числовые значения
                volume_length = material.get('volume_length_mm', 0)
                volume_weight = material.get('volume_weight_kg', 0)
                
                formatted_material = {
                    **material,
                    'arrival_date_display': arrival_date,
                    'cert_date_display': cert_date,
                    'volume_length_display': f"{volume_length:.0f}" if volume_length else "0",
                    'volume_weight_display': f"{volume_weight:.0f}" if volume_weight else "0",
                    'needs_lab_display': 'Да' if material.get('needs_lab') else '',
                    'otk_remarks_display': material.get('otk_remarks') or ''
                }
                
                formatted_materials.append(formatted_material)
            
            logger.debug(f"Отформатировано {len(formatted_materials)} материалов")
            return formatted_materials
            
        except Exception as e:
            logger.error(f"Ошибка форматирования материалов: {e}")
            return materials  # Возвращаем исходные данные при ошибке
    
    def search_materials_with_formatting(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Выполняет поиск материалов и форматирует результаты.
        
        Args:
            search_term: Поисковый запрос
            
        Returns:
            Отформатированный список найденных материалов
        """
        try:
            # Выполняем поиск
            materials = self.search_materials(search_term)
            
            # Форматируем для отображения
            formatted_materials = self.format_materials_for_display(materials)
            
            return formatted_materials
            
        except Exception as e:
            logger.error(f"Ошибка поиска с форматированием: {e}")
            raise 