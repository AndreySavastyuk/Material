"""
Сервис для работы с прикрепленными файлами к результатам испытаний.

Предоставляет функциональность для:
- Загрузка файлов к результатам тестов
- Управление файлами (просмотр, скачивание, удаление)
- Контроль размера и типов файлов
- Безопасность файловых операций
"""

import os
import shutil
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import sqlite3

from utils.logger import get_logger
from utils.exceptions import ValidationError, BusinessLogicError

logger = get_logger(__name__)


class FileAttachmentService:
    """
    Сервис для работы с прикрепленными файлами.
    """
    
    # Разрешенные типы файлов
    ALLOWED_EXTENSIONS = {
        # Изображения
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
        # Документы
        '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
        # Таблицы
        '.xls', '.xlsx', '.csv', '.ods',
        # Видео (для записи испытаний)
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv',
        # Архивы
        '.zip', '.rar', '.7z', '.tar', '.gz',
        # Специализированные форматы
        '.dwg', '.dxf', '.step', '.stp', '.iges', '.igs'
    }
    
    # Максимальный размер файла (100 МБ)
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    def __init__(self, db_connection, attachments_dir: str = "attachments"):
        """
        Инициализация сервиса.
        
        Args:
            db_connection: Подключение к базе данных
            attachments_dir: Директория для хранения файлов
        """
        self.db_connection = db_connection
        self.attachments_dir = Path(attachments_dir)
        
        # Создаем директорию для файлов если не существует
        self.attachments_dir.mkdir(exist_ok=True)
        
        # Инициализируем mimetypes
        mimetypes.init()
    
    def upload_file(self, request_id: int, test_name: str, file_path: str, 
                   description: str, user_login: str) -> int:
        """
        Загрузка файла к результатам теста.
        
        Args:
            request_id: ID заявки
            test_name: Название теста
            file_path: Путь к исходному файлу
            description: Описание файла
            user_login: Логин пользователя
            
        Returns:
            ID созданной записи о файле
        """
        try:
            # Валидация входных данных
            if not os.path.exists(file_path):
                raise ValidationError("Файл не найден")
            
            # Проверяем размер файла
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_FILE_SIZE:
                raise ValidationError(f"Размер файла превышает максимально допустимый ({self.MAX_FILE_SIZE // (1024*1024)} МБ)")
            
            # Получаем информацию о файле
            file_name = os.path.basename(file_path)
            file_ext = Path(file_path).suffix.lower()
            
            # Проверяем расширение файла
            if file_ext not in self.ALLOWED_EXTENSIONS:
                raise ValidationError(f"Тип файла {file_ext} не разрешен")
            
            # Определяем MIME-тип
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Проверяем существование заявки
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM lab_requests WHERE id = ?", (request_id,))
            if not cursor.fetchone():
                raise ValidationError(f"Заявка с ID {request_id} не найдена")
            
            # Генерируем уникальное имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_hash = self._calculate_file_hash(file_path)[:8]
            safe_filename = self._sanitize_filename(file_name)
            new_filename = f"{timestamp}_{file_hash}_{safe_filename}"
            
            # Создаем структуру директорий
            request_dir = self.attachments_dir / str(request_id) / test_name.replace(" ", "_")
            request_dir.mkdir(parents=True, exist_ok=True)
            
            # Копируем файл
            destination_path = request_dir / new_filename
            shutil.copy2(file_path, destination_path)
            
            # Сохраняем информацию в БД
            cursor.execute("""
                INSERT INTO request_attachments 
                (request_id, test_name, file_name, file_path, file_size, 
                 file_type, mime_type, description, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, test_name, file_name, str(destination_path),
                file_size, file_ext, mime_type, description, user_login
            ))
            
            attachment_id = cursor.lastrowid
            self.db_connection.commit()
            
            logger.info(f"Файл {file_name} загружен для заявки {request_id}, тест {test_name}")
            return attachment_id
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка загрузки файла: {e}")
            raise BusinessLogicError(
                message="Ошибка загрузки файла",
                original_error=e
            )
    
    def get_attachments(self, request_id: int, test_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка прикрепленных файлов.
        
        Args:
            request_id: ID заявки
            test_name: Название теста (если None - все файлы заявки)
            
        Returns:
            Список файлов
        """
        try:
            cursor = self.db_connection.cursor()
            
            if test_name:
                cursor.execute("""
                    SELECT id, test_name, file_name, file_path, file_size, 
                           file_type, mime_type, description, uploaded_by, uploaded_at
                    FROM request_attachments
                    WHERE request_id = ? AND test_name = ? AND is_deleted = 0
                    ORDER BY uploaded_at DESC
                """, (request_id, test_name))
            else:
                cursor.execute("""
                    SELECT id, test_name, file_name, file_path, file_size, 
                           file_type, mime_type, description, uploaded_by, uploaded_at
                    FROM request_attachments
                    WHERE request_id = ? AND is_deleted = 0
                    ORDER BY test_name, uploaded_at DESC
                """, (request_id,))
            
            attachments = []
            for row in cursor.fetchall():
                # Проверяем существование файла
                file_exists = os.path.exists(row['file_path'])
                
                attachments.append({
                    'id': row['id'],
                    'test_name': row['test_name'],
                    'file_name': row['file_name'],
                    'file_path': row['file_path'],
                    'file_size': row['file_size'],
                    'file_size_formatted': self._format_file_size(row['file_size']),
                    'file_type': row['file_type'],
                    'mime_type': row['mime_type'],
                    'description': row['description'],
                    'uploaded_by': row['uploaded_by'],
                    'uploaded_at': row['uploaded_at'],
                    'file_exists': file_exists,
                    'is_image': self._is_image_file(row['mime_type']),
                    'is_viewable': self._is_viewable_file(row['mime_type'])
                })
            
            return attachments
            
        except Exception as e:
            logger.error(f"Ошибка получения прикрепленных файлов: {e}")
            return []
    
    def get_attachment(self, attachment_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о конкретном файле.
        
        Args:
            attachment_id: ID файла
            
        Returns:
            Информация о файле или None
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT id, request_id, test_name, file_name, file_path, file_size, 
                       file_type, mime_type, description, uploaded_by, uploaded_at
                FROM request_attachments
                WHERE id = ? AND is_deleted = 0
            """, (attachment_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'request_id': row['request_id'],
                    'test_name': row['test_name'],
                    'file_name': row['file_name'],
                    'file_path': row['file_path'],
                    'file_size': row['file_size'],
                    'file_size_formatted': self._format_file_size(row['file_size']),
                    'file_type': row['file_type'],
                    'mime_type': row['mime_type'],
                    'description': row['description'],
                    'uploaded_by': row['uploaded_by'],
                    'uploaded_at': row['uploaded_at'],
                    'file_exists': os.path.exists(row['file_path']),
                    'is_image': self._is_image_file(row['mime_type']),
                    'is_viewable': self._is_viewable_file(row['mime_type'])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о файле {attachment_id}: {e}")
            return None
    
    def delete_attachment(self, attachment_id: int, user_login: str, 
                         hard_delete: bool = False) -> bool:
        """
        Удаление прикрепленного файла.
        
        Args:
            attachment_id: ID файла
            user_login: Логин пользователя
            hard_delete: Физическое удаление файла
            
        Returns:
            True если удаление успешно
        """
        try:
            # Получаем информацию о файле
            attachment = self.get_attachment(attachment_id)
            if not attachment:
                raise ValidationError("Файл не найден")
            
            # Проверяем права на удаление (только автор или администратор)
            if attachment['uploaded_by'] != user_login:
                # TODO: добавить проверку роли администратора
                raise ValidationError("Нет прав на удаление этого файла")
            
            cursor = self.db_connection.cursor()
            
            if hard_delete:
                # Физическое удаление
                try:
                    if os.path.exists(attachment['file_path']):
                        os.remove(attachment['file_path'])
                except OSError as e:
                    logger.warning(f"Не удалось удалить файл {attachment['file_path']}: {e}")
                
                cursor.execute("DELETE FROM request_attachments WHERE id = ?", (attachment_id,))
            else:
                # Мягкое удаление (помечаем как удаленный)
                cursor.execute("""
                    UPDATE request_attachments 
                    SET is_deleted = 1 
                    WHERE id = ?
                """, (attachment_id,))
            
            self.db_connection.commit()
            
            logger.info(f"Файл {attachment['file_name']} удален пользователем {user_login}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка удаления файла: {e}")
            return False
    
    def get_file_content(self, attachment_id: int) -> Optional[bytes]:
        """
        Получение содержимого файла для просмотра/скачивания.
        
        Args:
            attachment_id: ID файла
            
        Returns:
            Содержимое файла в байтах или None
        """
        try:
            attachment = self.get_attachment(attachment_id)
            if not attachment or not attachment['file_exists']:
                return None
            
            with open(attachment['file_path'], 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Ошибка чтения файла {attachment_id}: {e}")
            return None
    
    def update_attachment_description(self, attachment_id: int, description: str, 
                                    user_login: str) -> bool:
        """
        Обновление описания файла.
        
        Args:
            attachment_id: ID файла
            description: Новое описание
            user_login: Логин пользователя
            
        Returns:
            True если обновление успешно
        """
        try:
            # Проверяем права на редактирование
            attachment = self.get_attachment(attachment_id)
            if not attachment:
                raise ValidationError("Файл не найден")
            
            if attachment['uploaded_by'] != user_login:
                raise ValidationError("Нет прав на редактирование этого файла")
            
            cursor = self.db_connection.cursor()
            cursor.execute("""
                UPDATE request_attachments 
                SET description = ? 
                WHERE id = ?
            """, (description, attachment_id))
            
            self.db_connection.commit()
            
            logger.info(f"Обновлено описание файла {attachment_id}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка обновления описания файла: {e}")
            return False
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики использования хранилища.
        
        Returns:
            Статистика хранилища
        """
        try:
            cursor = self.db_connection.cursor()
            
            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_files,
                    SUM(file_size) as total_size,
                    COUNT(DISTINCT request_id) as requests_with_files,
                    COUNT(DISTINCT uploaded_by) as uploaders
                FROM request_attachments
                WHERE is_deleted = 0
            """)
            
            row = cursor.fetchone()
            
            # Статистика по типам файлов
            cursor.execute("""
                SELECT file_type, COUNT(*) as count, SUM(file_size) as size
                FROM request_attachments
                WHERE is_deleted = 0
                GROUP BY file_type
                ORDER BY size DESC
            """)
            
            file_types = cursor.fetchall()
            
            # Статистика по пользователям
            cursor.execute("""
                SELECT uploaded_by, COUNT(*) as count, SUM(file_size) as size
                FROM request_attachments
                WHERE is_deleted = 0
                GROUP BY uploaded_by
                ORDER BY size DESC
                LIMIT 10
            """)
            
            top_uploaders = cursor.fetchall()
            
            return {
                'total_files': row['total_files'] or 0,
                'total_size': row['total_size'] or 0,
                'total_size_formatted': self._format_file_size(row['total_size'] or 0),
                'requests_with_files': row['requests_with_files'] or 0,
                'uploaders': row['uploaders'] or 0,
                'file_types': [
                    {
                        'type': ft['file_type'],
                        'count': ft['count'],
                        'size': ft['size'],
                        'size_formatted': self._format_file_size(ft['size'])
                    }
                    for ft in file_types
                ],
                'top_uploaders': [
                    {
                        'user': tu['uploaded_by'],
                        'count': tu['count'],
                        'size': tu['size'],
                        'size_formatted': self._format_file_size(tu['size'])
                    }
                    for tu in top_uploaders
                ]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики хранилища: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'total_size_formatted': '0 Б',
                'requests_with_files': 0,
                'uploaders': 0,
                'file_types': [],
                'top_uploaders': []
            }
    
    def cleanup_orphaned_files(self) -> int:
        """
        Очистка файлов-сирот (файлы без записей в БД).
        
        Returns:
            Количество удаленных файлов
        """
        try:
            # Получаем все файлы из БД
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT file_path FROM request_attachments WHERE is_deleted = 0")
            db_files = {row['file_path'] for row in cursor.fetchall()}
            
            # Сканируем файловую систему
            deleted_count = 0
            for root, dirs, files in os.walk(self.attachments_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path not in db_files:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            logger.debug(f"Удален файл-сирота: {file_path}")
                        except OSError as e:
                            logger.warning(f"Не удалось удалить файл-сироту {file_path}: {e}")
            
            # Удаляем пустые директории
            for root, dirs, files in os.walk(self.attachments_dir, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Директория пуста
                            os.rmdir(dir_path)
                            logger.debug(f"Удалена пустая директория: {dir_path}")
                    except OSError:
                        pass  # Директория не пуста или ошибка доступа
            
            logger.info(f"Очистка завершена. Удалено {deleted_count} файлов-сирот")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки файлов-сирот: {e}")
            return 0
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Вычисление SHA256 хеша файла."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return "unknown"
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла от опасных символов."""
        # Удаляем опасные символы
        dangerous_chars = '<>:"/\\|?*'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Ограничиваем длину
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext
        
        return filename
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Форматирование размера файла в человекочитаемый вид."""
        if size_bytes == 0:
            return "0 Б"
        
        size_names = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def _is_image_file(self, mime_type: str) -> bool:
        """Проверка, является ли файл изображением."""
        return mime_type.startswith('image/')
    
    def _is_viewable_file(self, mime_type: str) -> bool:
        """Проверка, можно ли просматривать файл в браузере."""
        viewable_types = {
            'text/plain', 'text/html', 'text/css', 'text/javascript',
            'application/pdf', 'application/json'
        }
        return mime_type in viewable_types or self._is_image_file(mime_type) 