"""
Базовый класс для всех репозиториев.
Содержит общие CRUD операции и типы данных.
"""

from typing import Dict, List, Optional, Any, Type, Union
from abc import ABC, abstractmethod
import sqlite3
from utils.logger import get_logger

# Получаем логгер для репозиториев
logger = get_logger('repositories')


class BaseRepository(ABC):
    """
    Базовый класс для работы с БД.
    Все репозитории должны наследоваться от этого класса.
    """
    
    def __init__(self, connection: sqlite3.Connection):
        """
        Инициализация репозитория.
        
        Args:
            connection: Подключение к БД
        """
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """Название таблицы в БД."""
        pass
    
    @property
    @abstractmethod
    def primary_key(self) -> str:
        """Название первичного ключа."""
        pass
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Создание новой записи.
        
        Args:
            data: Данные для создания записи
            
        Returns:
            ID созданной записи
            
        Raises:
            sqlite3.Error: Ошибка при работе с БД
        """
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data.keys()])
            values = list(data.values())
            
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            
            cursor = self._connection.execute(query, values)
            self._connection.commit()
            
            logger.info(f"Создана запись в {self.table_name}, ID: {cursor.lastrowid}")
            return cursor.lastrowid
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при создании записи в {self.table_name}: {e}")
            self._connection.rollback()
            raise
    
    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение записи по ID.
        
        Args:
            record_id: ID записи
            
        Returns:
            Словарь с данными записи или None
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?"
            cursor = self._connection.execute(query, (record_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении записи из {self.table_name}: {e}")
            raise
    
    def get_all(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Получение всех записей с опциональными фильтрами.
        
        Args:
            filters: Фильтры для запроса
            
        Returns:
            Список словарей с данными записей
        """
        try:
            query = f"SELECT * FROM {self.table_name}"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is not None:
                        conditions.append(f"{key} = ?")
                        params.append(value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            cursor = self._connection.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении записей из {self.table_name}: {e}")
            raise
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """
        Обновление записи.
        
        Args:
            record_id: ID записи
            data: Данные для обновления
            
        Returns:
            True если запись обновлена, False если не найдена
        """
        try:
            if not data:
                return False
                
            set_clauses = []
            values = []
            
            for key, value in data.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            values.append(record_id)
            
            query = f"UPDATE {self.table_name} SET {', '.join(set_clauses)} WHERE {self.primary_key} = ?"
            
            cursor = self._connection.execute(query, values)
            self._connection.commit()
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Обновлена запись в {self.table_name}, ID: {record_id}")
            else:
                logger.warning(f"Запись не найдена в {self.table_name}, ID: {record_id}")
                
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении записи в {self.table_name}: {e}")
            self._connection.rollback()
            raise
    
    def delete(self, record_id: int) -> bool:
        """
        Удаление записи.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись удалена, False если не найдена
        """
        try:
            query = f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?"
            
            cursor = self._connection.execute(query, (record_id,))
            self._connection.commit()
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Удалена запись из {self.table_name}, ID: {record_id}")
            else:
                logger.warning(f"Запись не найдена в {self.table_name}, ID: {record_id}")
                
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при удалении записи из {self.table_name}: {e}")
            self._connection.rollback()
            raise
    
    def soft_delete(self, record_id: int) -> bool:
        """
        Мягкое удаление записи (установка флага to_delete).
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись помечена, False если не найдена
        """
        return self.update(record_id, {'to_delete': 1})
    
    def restore(self, record_id: int) -> bool:
        """
        Восстановление мягко удаленной записи.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись восстановлена, False если не найдена
        """
        return self.update(record_id, {'to_delete': 0})
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Подсчет количества записей.
        
        Args:
            filters: Фильтры для запроса
            
        Returns:
            Количество записей
        """
        try:
            query = f"SELECT COUNT(*) FROM {self.table_name}"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is not None:
                        conditions.append(f"{key} = ?")
                        params.append(value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            cursor = self._connection.execute(query, params)
            return cursor.fetchone()[0]
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при подсчете записей в {self.table_name}: {e}")
            raise
    
    def exists(self, record_id: int) -> bool:
        """
        Проверка существования записи.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если запись существует
        """
        return self.get_by_id(record_id) is not None
    
    def execute_custom_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Выполнение кастомного запроса.
        
        Args:
            query: SQL запрос
            params: Параметры для запроса
            
        Returns:
            Результат запроса
        """
        try:
            cursor = self._connection.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при выполнении кастомного запроса: {e}")
            raise 