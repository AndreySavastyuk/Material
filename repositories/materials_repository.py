"""
Репозиторий для работы с материалами.
Содержит все операции CRUD и специфические бизнес-методы для материалов.
"""

import os
import sqlite3
import datetime
import shutil
from typing import Dict, List, Optional, Any, Tuple
from repositories.base import BaseRepository
from utils.logger import get_logger

logger = get_logger('repositories.materials')


class MaterialsRepository(BaseRepository):
    """
    Репозиторий для работы с материалами.
    Предоставляет методы для CRUD операций и специфической бизнес-логики.
    """
    
    @property
    def table_name(self) -> str:
        """Название таблицы в БД."""
        return 'Materials'
    
    @property
    def primary_key(self) -> str:
        """Название первичного ключа."""
        return 'id'
    
    def __init__(self, connection: sqlite3.Connection, docs_root: str = None):
        """
        Инициализация репозитория материалов.
        
        Args:
            connection: Подключение к БД
            docs_root: Корневая папка для документов
        """
        super().__init__(connection)
        self.docs_root = docs_root or os.path.join(os.getcwd(), 'docs')
    
    def get_materials_with_relations(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Получает материалы с данными из связанных таблиц.
        
        Args:
            include_deleted: Включать помеченные на удаление материалы
            
        Returns:
            Список материалов с данными поставщиков, марок и типов проката
        """
        try:
            # Определяем существующие колонки в Materials
            cursor = self._connection.cursor()
            cursor.execute("PRAGMA table_info(Materials)")
            existing_columns = {col[1] for col in cursor.fetchall()}
            
            # Функция для безопасного получения колонки
            def safe_column(name: str, default: str = "''", table: str = "m") -> str:
                if name in existing_columns:
                    return f"{table}.{name}"
                return f"{default} AS {name}"
            
            # Формируем список колонок
            select_columns = [
                "m.id",
                safe_column('arrival_date'),
                "COALESCE(s.name, '') AS supplier",
                safe_column('order_num'),
                "COALESCE(g.grade, '') AS grade",
                "COALESCE(rt.type, '') AS rolling_type",
                safe_column('size'),
                safe_column('cert_num'),
                safe_column('cert_date'),
                safe_column('batch'),
                safe_column('heat_num'),
                f"COALESCE({safe_column('volume_length_mm', '0')}, 0) AS volume_length_mm",
                f"COALESCE({safe_column('volume_weight_kg', '0')}, 0) AS volume_weight_kg",
                safe_column('otk_remarks'),
                safe_column('needs_lab', '0'),
                safe_column('cert_scan_path'),
                safe_column('cert_saved_at'),
                safe_column('to_delete', '0'),
                safe_column('supplier_id', 'NULL'),
                safe_column('grade_id', 'NULL'),
                safe_column('rolling_type_id', 'NULL')
            ]
            
            query = f"""
                SELECT {', '.join(select_columns)}
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                LEFT JOIN Grades g ON m.grade_id = g.id
                LEFT JOIN RollingTypes rt ON m.rolling_type_id = rt.id
            """
            
            if not include_deleted:
                query += " WHERE COALESCE(m.to_delete, 0) = 0"
            
            query += " ORDER BY m.id"
            
            cursor.execute(query)
            materials = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"Получено {len(materials)} материалов")
            return materials
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении материалов: {e}")
            raise
    
    def create_material(self, material_data: Dict[str, Any]) -> int:
        """
        Создает новый материал.
        
        Args:
            material_data: Данные материала
            
        Returns:
            ID созданного материала
        """
        try:
            # Валидация обязательных полей
            required_fields = ['arrival_date', 'supplier_id', 'grade_id']
            for field in required_fields:
                if field not in material_data:
                    raise ValueError(f"Обязательное поле '{field}' отсутствует")
            
            # Создание материала с валидацией
            with self._connection:
                material_id = self.create(material_data)
                logger.info(f"Создан материал с ID: {material_id}")
                return material_id
                
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Ошибка при создании материала: {e}")
            raise
    
    def update_material(self, material_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Обновляет материал.
        
        Args:
            material_id: ID материала
            update_data: Данные для обновления
            
        Returns:
            True если материал обновлен, False если не найден
        """
        try:
            # Проверяем существование материала
            if not self.exists(material_id):
                logger.warning(f"Материал с ID {material_id} не найден")
                return False
            
            # Обновляем материал в транзакции
            with self._connection:
                success = self.update(material_id, update_data)
                if success:
                    logger.info(f"Обновлен материал с ID: {material_id}")
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении материала {material_id}: {e}")
            raise
    
    def mark_for_deletion(self, material_id: int) -> bool:
        """
        Помечает материал на удаление (soft delete).
        
        Args:
            material_id: ID материала
            
        Returns:
            True если материал помечен, False если не найден
        """
        try:
            with self._connection:
                success = self.soft_delete(material_id)
                if success:
                    logger.info(f"Материал {material_id} помечен на удаление")
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при пометке материала {material_id} на удаление: {e}")
            raise
    
    def unmark_for_deletion(self, material_id: int) -> bool:
        """
        Снимает пометку удаления с материала.
        
        Args:
            material_id: ID материала
            
        Returns:
            True если пометка снята, False если не найден
        """
        try:
            with self._connection:
                success = self.restore(material_id)
                if success:
                    logger.info(f"С материала {material_id} снята пометка удаления")
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при снятии пометки удаления с материала {material_id}: {e}")
            raise
    
    def get_marked_for_deletion(self) -> List[Dict[str, Any]]:
        """
        Получает материалы, помеченные на удаление.
        
        Returns:
            Список материалов с пометкой удаления
        """
        try:
            query = """
                SELECT m.id, m.arrival_date, s.name AS supplier, m.order_num
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                WHERE m.to_delete = 1
                ORDER BY m.id
            """
            
            cursor = self._connection.execute(query)
            materials = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"Получено {len(materials)} материалов, помеченных на удаление")
            return materials
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении материалов на удаление: {e}")
            raise
    
    def permanently_delete_material(self, material_id: int) -> bool:
        """
        Физически удаляет материал и связанные документы.
        
        Args:
            material_id: ID материала
            
        Returns:
            True если материал удален, False если не найден
        """
        try:
            with self._connection:
                # Удаляем связанные документы
                self._connection.execute(
                    "DELETE FROM Documents WHERE material_id = ?",
                    (material_id,)
                )
                
                # Удаляем связанные дефекты
                self._connection.execute(
                    "DELETE FROM defects WHERE material_id = ?",
                    (material_id,)
                )
                
                # Удаляем лабораторные запросы
                self._connection.execute(
                    "DELETE FROM lab_requests WHERE material_id = ?",
                    (material_id,)
                )
                
                # Удаляем блокировки
                self._connection.execute(
                    "DELETE FROM RecordLocks WHERE material_id = ?",
                    (material_id,)
                )
                
                # Удаляем сам материал
                success = self.delete(material_id)
                
                if success:
                    logger.info(f"Материал {material_id} физически удален")
                    
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при физическом удалении материала {material_id}: {e}")
            raise
    
    def acquire_lock(self, material_id: int, user_login: str) -> bool:
        """
        Захватывает блокировку на материал.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если блокировка захвачена, False если уже заблокирован
        """
        try:
            with self._connection:
                # Проверяем, нет ли уже блокировки
                cursor = self._connection.execute(
                    "SELECT locked_by FROM RecordLocks WHERE material_id = ?",
                    (material_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    logger.warning(f"Материал {material_id} уже заблокирован пользователем {row['locked_by']}")
                    return False
                
                # Создаем блокировку
                now = datetime.datetime.now().isoformat()
                self._connection.execute(
                    "INSERT INTO RecordLocks(material_id, locked_by, locked_at) VALUES(?, ?, ?)",
                    (material_id, user_login, now)
                )
                
                logger.info(f"Материал {material_id} заблокирован пользователем {user_login}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при захвате блокировки материала {material_id}: {e}")
            raise
    
    def release_lock(self, material_id: int, user_login: str) -> bool:
        """
        Освобождает блокировку материала.
        
        Args:
            material_id: ID материала
            user_login: Логин пользователя
            
        Returns:
            True если блокировка освобождена, False если не найдена
        """
        try:
            with self._connection:
                cursor = self._connection.execute(
                    "DELETE FROM RecordLocks WHERE material_id = ? AND locked_by = ?",
                    (material_id, user_login)
                )
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Блокировка материала {material_id} освобождена пользователем {user_login}")
                else:
                    logger.warning(f"Блокировка материала {material_id} не найдена для пользователя {user_login}")
                    
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при освобождении блокировки материала {material_id}: {e}")
            raise
    
    def is_locked(self, material_id: int) -> Tuple[bool, str]:
        """
        Проверяет, заблокирован ли материал.
        
        Args:
            material_id: ID материала
            
        Returns:
            Кортеж (заблокирован, логин_пользователя)
        """
        try:
            cursor = self._connection.execute(
                "SELECT locked_by FROM RecordLocks WHERE material_id = ?",
                (material_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return True, row['locked_by']
            return False, ''
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при проверке блокировки материала {material_id}: {e}")
            raise
    
    def get_documents(self, material_id: int) -> List[Dict[str, Any]]:
        """
        Получает документы материала.
        
        Args:
            material_id: ID материала
            
        Returns:
            Список документов
        """
        try:
            cursor = self._connection.execute(
                "SELECT * FROM Documents WHERE material_id = ? ORDER BY upload_date DESC",
                (material_id,)
            )
            documents = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"Получено {len(documents)} документов для материала {material_id}")
            return documents
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении документов материала {material_id}: {e}")
            raise
    
    def add_document(self, material_id: int, doc_type: str, src_path: str, 
                    uploaded_by: str) -> int:
        """
        Добавляет документ к материалу.
        
        Args:
            material_id: ID материала
            doc_type: Тип документа
            src_path: Путь к исходному файлу
            uploaded_by: Кто загрузил документ
            
        Returns:
            ID созданного документа
        """
        try:
            with self._connection:
                # Создаем папку для документов материала
                folder = os.path.join(self.docs_root, str(material_id))
                os.makedirs(folder, exist_ok=True)
                
                # Определяем путь для сохранения
                fname = os.path.basename(src_path)
                dst = os.path.join(folder, fname)
                
                # Проверяем уникальность имени файла
                base, ext = os.path.splitext(fname)
                idx = 1
                while os.path.exists(dst):
                    dst = os.path.join(folder, f"{base}_{idx}{ext}")
                    idx += 1
                
                # Копируем файл
                shutil.copy2(src_path, dst)
                
                # Сохраняем информацию в БД
                upload_date = datetime.datetime.now().isoformat()
                cursor = self._connection.execute(
                    """
                    INSERT INTO Documents(material_id, doc_type, file_path, upload_date, uploaded_by)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (material_id, doc_type, dst, upload_date, uploaded_by)
                )
                
                document_id = cursor.lastrowid
                logger.info(f"Добавлен документ {document_id} к материалу {material_id}")
                return document_id
                
        except (sqlite3.Error, OSError) as e:
            logger.error(f"Ошибка при добавлении документа к материалу {material_id}: {e}")
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
            materials = self.get_materials_with_relations()
            supplier_materials = [m for m in materials if m.get('supplier_id') == supplier_id]
            
            logger.info(f"Получено {len(supplier_materials)} материалов поставщика {supplier_id}")
            return supplier_materials
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении материалов поставщика {supplier_id}: {e}")
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
            materials = self.get_materials_with_relations()
            grade_materials = [m for m in materials if m.get('grade_id') == grade_id]
            
            logger.info(f"Получено {len(grade_materials)} материалов марки {grade_id}")
            return grade_materials
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении материалов марки {grade_id}: {e}")
            raise
    
    def get_materials_needing_lab_tests(self) -> List[Dict[str, Any]]:
        """
        Получает материалы, требующие лабораторных испытаний.
        
        Returns:
            Список материалов для лабораторных испытаний
        """
        try:
            materials = self.get_materials_with_relations()
            lab_materials = [m for m in materials if m.get('needs_lab') == 1]
            
            logger.info(f"Получено {len(lab_materials)} материалов для лабораторных испытаний")
            return lab_materials
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении материалов для лабораторных испытаний: {e}")
            raise
    
    def search_materials(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Поиск материалов по различным полям.
        
        Args:
            search_term: Поисковый запрос
            
        Returns:
            Список найденных материалов
        """
        try:
            if len(search_term) < 2:
                return []
            
            search_pattern = f"%{search_term}%"
            
            query = """
                SELECT m.*, s.name AS supplier, g.grade, rt.type AS rolling_type
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                LEFT JOIN Grades g ON m.grade_id = g.id
                LEFT JOIN RollingTypes rt ON m.rolling_type_id = rt.id
                WHERE (
                    s.name LIKE ? OR
                    g.grade LIKE ? OR
                    rt.type LIKE ? OR
                    m.order_num LIKE ? OR
                    m.cert_num LIKE ? OR
                    m.batch LIKE ? OR
                    m.heat_num LIKE ? OR
                    m.size LIKE ?
                )
                AND COALESCE(m.to_delete, 0) = 0
                ORDER BY m.id
            """
            
            params = [search_pattern] * 8
            cursor = self._connection.execute(query, params)
            materials = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"Найдено {len(materials)} материалов по запросу: {search_term}")
            return materials
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при поиске материалов: {e}")
            raise
    
    def get_materials_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по материалам.
        
        Returns:
            Словарь с различными показателями
        """
        try:
            cursor = self._connection.cursor()
            
            # Общее количество материалов
            cursor.execute("SELECT COUNT(*) FROM Materials WHERE COALESCE(to_delete, 0) = 0")
            total_materials = cursor.fetchone()[0]
            
            # Количество помеченных на удаление
            cursor.execute("SELECT COUNT(*) FROM Materials WHERE to_delete = 1")
            marked_for_deletion = cursor.fetchone()[0]
            
            # Количество материалов, требующих лабораторных испытаний
            cursor.execute("SELECT COUNT(*) FROM Materials WHERE needs_lab = 1 AND COALESCE(to_delete, 0) = 0")
            needs_lab_tests = cursor.fetchone()[0]
            
            # Статистика по поставщикам
            cursor.execute("""
                SELECT s.name, COUNT(m.id) as count
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                WHERE COALESCE(m.to_delete, 0) = 0
                GROUP BY s.name
                ORDER BY count DESC
                LIMIT 10
            """)
            top_suppliers = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
            
            # Статистика по маркам
            cursor.execute("""
                SELECT g.grade, COUNT(m.id) as count
                FROM Materials m
                LEFT JOIN Grades g ON m.grade_id = g.id
                WHERE COALESCE(m.to_delete, 0) = 0
                GROUP BY g.grade
                ORDER BY count DESC
                LIMIT 10
            """)
            top_grades = [{'grade': row[0], 'count': row[1]} for row in cursor.fetchall()]
            
            stats = {
                'total_materials': total_materials,
                'marked_for_deletion': marked_for_deletion,
                'needs_lab_tests': needs_lab_tests,
                'top_suppliers': top_suppliers,
                'top_grades': top_grades
            }
            
            logger.info(f"Получена статистика: {total_materials} материалов")
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """
        Выполняет SQL запрос и возвращает результаты.
        
        Args:
            query: SQL запрос
            params: Параметры запроса (опционально)
            
        Returns:
            Список кортежей с результатами запроса
            
        Raises:
            sqlite3.Error: При ошибке выполнения запроса
        """
        try:
            cursor = self._connection.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            
            logger.debug(f"Выполнен запрос: {query[:100]}... Результатов: {len(results)}")
            return results
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            logger.error(f"Запрос: {query}")
            raise 