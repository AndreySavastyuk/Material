"""
Сервис для работы с черновиками заявок лаборатории.

Предоставляет функциональность для:
- Автосохранение черновиков
- Управление версиями данных
- История изменений с возможностью отката
- Настройки автосохранения пользователя
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import difflib
import copy

from utils.logger import get_logger
from utils.exceptions import ValidationError, BusinessLogicError

logger = get_logger(__name__)


class RequestDraftService:
    """
    Сервис для работы с черновиками и версиями заявок.
    """
    
    def __init__(self, db_connection):
        """
        Инициализация сервиса.
        
        Args:
            db_connection: Подключение к базе данных
        """
        self.db_connection = db_connection
    
    def get_autosave_settings(self, user_login: str) -> Dict[str, Any]:
        """
        Получение настроек автосохранения пользователя.
        
        Args:
            user_login: Логин пользователя
            
        Returns:
            Словарь с настройками автосохранения
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT autosave_enabled, autosave_interval, max_drafts
                FROM autosave_settings
                WHERE user_login = ?
            """, (user_login,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'autosave_enabled': bool(row['autosave_enabled']),
                    'autosave_interval': row['autosave_interval'],
                    'max_drafts': row['max_drafts']
                }
            else:
                # Создаем настройки по умолчанию
                default_settings = {
                    'autosave_enabled': True,
                    'autosave_interval': 300,  # 5 минут
                    'max_drafts': 10
                }
                self.save_autosave_settings(user_login, default_settings)
                return default_settings
                
        except Exception as e:
            logger.error(f"Ошибка получения настроек автосохранения: {e}")
            return {
                'autosave_enabled': True,
                'autosave_interval': 300,
                'max_drafts': 10
            }
    
    def save_autosave_settings(self, user_login: str, settings: Dict[str, Any]) -> bool:
        """
        Сохранение настроек автосохранения пользователя.
        
        Args:
            user_login: Логин пользователя
            settings: Словарь с настройками
            
        Returns:
            True если сохранение успешно
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO autosave_settings 
                (user_login, autosave_enabled, autosave_interval, max_drafts)
                VALUES (?, ?, ?, ?)
            """, (
                user_login,
                settings.get('autosave_enabled', True),
                settings.get('autosave_interval', 300),
                settings.get('max_drafts', 10)
            ))
            
            self.db_connection.commit()
            logger.info(f"Настройки автосохранения сохранены для пользователя {user_login}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек автосохранения: {e}")
            return False
    
    def save_draft(self, request_id: int, draft_name: str, draft_data: Dict[str, Any], 
                   user_login: str, is_auto_save: bool = False) -> int:
        """
        Сохранение черновика заявки.
        
        Args:
            request_id: ID заявки
            draft_name: Название черновика
            draft_data: Данные черновика
            user_login: Логин пользователя
            is_auto_save: Флаг автосохранения
            
        Returns:
            ID созданного черновика
        """
        try:
            # Валидация данных
            if not draft_name.strip():
                raise ValidationError("Название черновика не может быть пустым")
            
            # Проверяем существование заявки
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM lab_requests WHERE id = ?", (request_id,))
            if not cursor.fetchone():
                raise ValidationError(f"Заявка с ID {request_id} не найдена")
            
            # Очистка старых автосохранений если превышен лимит
            if is_auto_save:
                self._cleanup_old_autosaves(request_id, user_login)
            
            # Сохранение черновика
            draft_json = json.dumps(draft_data, ensure_ascii=False, indent=2)
            
            cursor.execute("""
                INSERT OR REPLACE INTO request_drafts 
                (request_id, draft_name, draft_data, created_by, is_auto_save)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, draft_name, draft_json, user_login, is_auto_save))
            
            draft_id = cursor.lastrowid
            self.db_connection.commit()
            
            logger.info(f"Черновик '{draft_name}' сохранен для заявки {request_id}")
            return draft_id
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка сохранения черновика: {e}")
            raise BusinessLogicError(
                message="Ошибка сохранения черновика",
                original_error=e
            )
    
    def get_drafts(self, request_id: int, user_login: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка черновиков для заявки.
        
        Args:
            request_id: ID заявки
            user_login: Логин пользователя (если None - все черновики)
            
        Returns:
            Список черновиков
        """
        try:
            cursor = self.db_connection.cursor()
            
            if user_login:
                cursor.execute("""
                    SELECT id, draft_name, created_by, created_at, updated_at, is_auto_save
                    FROM request_drafts
                    WHERE request_id = ? AND created_by = ?
                    ORDER BY updated_at DESC
                """, (request_id, user_login))
            else:
                cursor.execute("""
                    SELECT id, draft_name, created_by, created_at, updated_at, is_auto_save
                    FROM request_drafts
                    WHERE request_id = ?
                    ORDER BY updated_at DESC
                """, (request_id,))
            
            drafts = []
            for row in cursor.fetchall():
                drafts.append({
                    'id': row['id'],
                    'draft_name': row['draft_name'],
                    'created_by': row['created_by'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'is_auto_save': bool(row['is_auto_save'])
                })
            
            return drafts
            
        except Exception as e:
            logger.error(f"Ошибка получения черновиков: {e}")
            return []
    
    def get_draft(self, draft_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение данных черновика по ID.
        
        Args:
            draft_id: ID черновика
            
        Returns:
            Данные черновика или None
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT id, request_id, draft_name, draft_data, created_by, 
                       created_at, updated_at, is_auto_save
                FROM request_drafts
                WHERE id = ?
            """, (draft_id,))
            
            row = cursor.fetchone()
            if row:
                draft_data = json.loads(row['draft_data'])
                return {
                    'id': row['id'],
                    'request_id': row['request_id'],
                    'draft_name': row['draft_name'],
                    'draft_data': draft_data,
                    'created_by': row['created_by'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'is_auto_save': bool(row['is_auto_save'])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения черновика {draft_id}: {e}")
            return None
    
    def delete_draft(self, draft_id: int, user_login: str) -> bool:
        """
        Удаление черновика.
        
        Args:
            draft_id: ID черновика
            user_login: Логин пользователя
            
        Returns:
            True если удаление успешно
        """
        try:
            cursor = self.db_connection.cursor()
            
            # Проверяем права на удаление
            cursor.execute("""
                SELECT created_by FROM request_drafts WHERE id = ?
            """, (draft_id,))
            
            row = cursor.fetchone()
            if not row:
                raise ValidationError("Черновик не найден")
            
            if row['created_by'] != user_login:
                raise ValidationError("Нет прав на удаление этого черновика")
            
            # Удаляем черновик
            cursor.execute("DELETE FROM request_drafts WHERE id = ?", (draft_id,))
            self.db_connection.commit()
            
            logger.info(f"Черновик {draft_id} удален пользователем {user_login}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка удаления черновика: {e}")
            return False
    
    def create_version(self, request_id: int, change_description: str, 
                      new_data: Dict[str, Any], old_data: Dict[str, Any], 
                      user_login: str) -> int:
        """
        Создание новой версии заявки.
        
        Args:
            request_id: ID заявки
            change_description: Описание изменений
            new_data: Новые данные
            old_data: Старые данные
            user_login: Логин пользователя
            
        Returns:
            Номер созданной версии
        """
        try:
            cursor = self.db_connection.cursor()
            
            # Получаем следующий номер версии
            cursor.execute("""
                SELECT COALESCE(MAX(version_number), 0) + 1 
                FROM request_versions WHERE request_id = ?
            """, (request_id,))
            
            version_number = cursor.fetchone()[0]
            
            # Анализируем изменения
            changed_fields = self._analyze_changes(old_data, new_data)
            
            # Создаем снимок данных
            data_snapshot = json.dumps(new_data, ensure_ascii=False, indent=2)
            changed_fields_json = json.dumps(changed_fields, ensure_ascii=False)
            
            # Сохраняем версию
            cursor.execute("""
                INSERT INTO request_versions 
                (request_id, version_number, change_description, data_snapshot, 
                 changed_fields, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request_id, version_number, change_description, 
                data_snapshot, changed_fields_json, user_login
            ))
            
            self.db_connection.commit()
            
            logger.info(f"Создана версия {version_number} для заявки {request_id}")
            return version_number
            
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка создания версии: {e}")
            raise BusinessLogicError(
                message="Ошибка создания версии заявки",
                original_error=e
            )
    
    def get_versions(self, request_id: int) -> List[Dict[str, Any]]:
        """
        Получение списка версий заявки.
        
        Args:
            request_id: ID заявки
            
        Returns:
            Список версий
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT id, version_number, change_description, created_by, 
                       created_at, changed_fields
                FROM request_versions
                WHERE request_id = ?
                ORDER BY version_number DESC
            """, (request_id,))
            
            versions = []
            for row in cursor.fetchall():
                changed_fields = json.loads(row['changed_fields']) if row['changed_fields'] else []
                versions.append({
                    'id': row['id'],
                    'version_number': row['version_number'],
                    'change_description': row['change_description'],
                    'created_by': row['created_by'],
                    'created_at': row['created_at'],
                    'changed_fields': changed_fields
                })
            
            return versions
            
        except Exception as e:
            logger.error(f"Ошибка получения версий: {e}")
            return []
    
    def get_version_data(self, version_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение данных конкретной версии.
        
        Args:
            version_id: ID версии
            
        Returns:
            Данные версии или None
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT request_id, version_number, data_snapshot, change_description,
                       created_by, created_at
                FROM request_versions
                WHERE id = ?
            """, (version_id,))
            
            row = cursor.fetchone()
            if row:
                data_snapshot = json.loads(row['data_snapshot'])
                return {
                    'request_id': row['request_id'],
                    'version_number': row['version_number'],
                    'data_snapshot': data_snapshot,
                    'change_description': row['change_description'],
                    'created_by': row['created_by'],
                    'created_at': row['created_at']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения данных версии {version_id}: {e}")
            return None
    
    def revert_to_version(self, request_id: int, version_id: int, 
                         user_login: str, reason: str) -> bool:
        """
        Откат к предыдущей версии.
        
        Args:
            request_id: ID заявки
            version_id: ID версии для отката
            user_login: Логин пользователя
            reason: Причина отката
            
        Returns:
            True если откат успешен
        """
        try:
            # Получаем данные версии для отката
            version_data = self.get_version_data(version_id)
            if not version_data:
                raise ValidationError("Версия не найдена")
            
            if version_data['request_id'] != request_id:
                raise ValidationError("Версия не принадлежит указанной заявке")
            
            # Получаем текущие данные заявки
            current_data = self._get_current_request_data(request_id)
            
            # Создаем новую версию с откатом
            change_description = f"Откат к версии {version_data['version_number']}. Причина: {reason}"
            
            self.create_version(
                request_id, change_description, 
                version_data['data_snapshot'], current_data, user_login
            )
            
            # Применяем данные из версии к заявке
            self._apply_version_to_request(request_id, version_data['data_snapshot'])
            
            logger.info(f"Выполнен откат заявки {request_id} к версии {version_data['version_number']}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка отката к версии: {e}")
            return False
    
    def _cleanup_old_autosaves(self, request_id: int, user_login: str):
        """Очистка старых автосохранений."""
        try:
            settings = self.get_autosave_settings(user_login)
            max_drafts = settings['max_drafts']
            
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT id FROM request_drafts
                WHERE request_id = ? AND created_by = ? AND is_auto_save = 1
                ORDER BY updated_at DESC
                LIMIT -1 OFFSET ?
            """, (request_id, user_login, max_drafts - 1))
            
            old_drafts = cursor.fetchall()
            if old_drafts:
                old_ids = [str(row['id']) for row in old_drafts]
                cursor.execute(f"""
                    DELETE FROM request_drafts 
                    WHERE id IN ({','.join(['?'] * len(old_ids))})
                """, old_ids)
                
                logger.debug(f"Удалено {len(old_drafts)} старых автосохранений")
                
        except Exception as e:
            logger.warning(f"Ошибка очистки старых автосохранений: {e}")
    
    def _analyze_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> List[str]:
        """Анализ изменений между версиями данных."""
        try:
            changed_fields = []
            
            def compare_nested(old_dict, new_dict, prefix=""):
                for key in set(list(old_dict.keys()) + list(new_dict.keys())):
                    old_val = old_dict.get(key)
                    new_val = new_dict.get(key)
                    field_name = f"{prefix}.{key}" if prefix else key
                    
                    if old_val != new_val:
                        if isinstance(old_val, dict) and isinstance(new_val, dict):
                            compare_nested(old_val, new_val, field_name)
                        else:
                            changed_fields.append(field_name)
            
            compare_nested(old_data, new_data)
            return changed_fields
            
        except Exception as e:
            logger.warning(f"Ошибка анализа изменений: {e}")
            return ["unknown_changes"]
    
    def _get_current_request_data(self, request_id: int) -> Dict[str, Any]:
        """Получение текущих данных заявки."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT scenario_id, tests_json, results_json, status
                FROM lab_requests
                WHERE id = ?
            """, (request_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'scenario_id': row['scenario_id'],
                    'tests': json.loads(row['tests_json']) if row['tests_json'] else [],
                    'results': json.loads(row['results_json']) if row['results_json'] else [],
                    'status': row['status']
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Ошибка получения текущих данных заявки: {e}")
            return {}
    
    def _apply_version_to_request(self, request_id: int, version_data: Dict[str, Any]):
        """Применение данных версии к заявке."""
        try:
            cursor = self.db_connection.cursor()
            
            # Обновляем основные поля заявки
            cursor.execute("""
                UPDATE lab_requests 
                SET scenario_id = ?, tests_json = ?, results_json = ?, status = ?
                WHERE id = ?
            """, (
                version_data.get('scenario_id'),
                json.dumps(version_data.get('tests', []), ensure_ascii=False),
                json.dumps(version_data.get('results', []), ensure_ascii=False),
                version_data.get('status'),
                request_id
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Ошибка применения версии к заявке: {e}")
            raise
    
    def get_draft_diff(self, draft_id: int, compare_with: str = "current") -> Optional[str]:
        """
        Получение различий между черновиком и текущими данными или другим черновиком.
        
        Args:
            draft_id: ID черновика
            compare_with: С чем сравнивать ("current", "draft_id")
            
        Returns:
            Текст различий в формате unified diff
        """
        try:
            draft = self.get_draft(draft_id)
            if not draft:
                return None
            
            draft_json = json.dumps(draft['draft_data'], indent=2, ensure_ascii=False, sort_keys=True)
            
            if compare_with == "current":
                current_data = self._get_current_request_data(draft['request_id'])
                current_json = json.dumps(current_data, indent=2, ensure_ascii=False, sort_keys=True)
                
                diff = difflib.unified_diff(
                    current_json.splitlines(keepends=True),
                    draft_json.splitlines(keepends=True),
                    fromfile="Текущая версия",
                    tofile=f"Черновик: {draft['draft_name']}",
                    lineterm=""
                )
                
                return "".join(diff)
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения различий: {e}")
            return None 