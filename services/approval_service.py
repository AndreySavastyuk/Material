"""
Сервис системы одобрения результатов лабораторных испытаний.

Предоставляет функциональность для:
- Многоуровневая система одобрения
- Workflow для различных типов тестов
- Контроль прав доступа по ролям
- Уведомления о необходимости одобрения
- История одобрений и отклонений
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from utils.logger import get_logger
from utils.exceptions import ValidationError, BusinessLogicError

logger = get_logger(__name__)


class ApprovalStatus(Enum):
    """Статусы одобрения."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"


class ApprovalService:
    """
    Сервис для управления системой одобрения результатов.
    """
    
    def __init__(self, db_connection):
        """
        Инициализация сервиса.
        
        Args:
            db_connection: Подключение к базе данных
        """
        self.db_connection = db_connection
    
    def get_approval_config(self, test_name: Optional[str] = None, 
                          material_grade: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение конфигурации одобрения для теста/материала.
        
        Args:
            test_name: Название теста
            material_grade: Марка материала
            
        Returns:
            Список правил одобрения
        """
        try:
            cursor = self.db_connection.cursor()
            
            # Получаем специфические правила для теста/материала
            if test_name and material_grade:
                cursor.execute("""
                    SELECT * FROM approval_config
                    WHERE (test_name = ? OR test_name IS NULL)
                    AND (material_grade = ? OR material_grade IS NULL)
                    ORDER BY test_name DESC, material_grade DESC, approval_level
                """, (test_name, material_grade))
            elif test_name:
                cursor.execute("""
                    SELECT * FROM approval_config
                    WHERE test_name = ? OR test_name IS NULL
                    ORDER BY test_name DESC, approval_level
                """, (test_name,))
            else:
                cursor.execute("""
                    SELECT * FROM approval_config
                    ORDER BY test_name, approval_level
                """)
            
            configs = []
            for row in cursor.fetchall():
                configs.append({
                    'id': row['id'],
                    'test_name': row['test_name'],
                    'material_grade': row['material_grade'],
                    'approval_level': row['approval_level'],
                    'approver_role': row['approver_role'],
                    'is_required': bool(row['is_required']),
                    'min_approvers': row['min_approvers']
                })
            
            return configs
            
        except Exception as e:
            logger.error(f"Ошибка получения конфигурации одобрения: {e}")
            return []
    
    def create_approval_request(self, request_id: int, test_name: Optional[str], 
                              user_login: str, material_grade: Optional[str] = None) -> bool:
        """
        Создание запроса на одобрение.
        
        Args:
            request_id: ID заявки
            test_name: Название теста (None для всей заявки)
            user_login: Логин пользователя
            material_grade: Марка материала
            
        Returns:
            True если запрос создан успешно
        """
        try:
            # Проверяем существование заявки
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM lab_requests WHERE id = ?", (request_id,))
            if not cursor.fetchone():
                raise ValidationError(f"Заявка с ID {request_id} не найдена")
            
            # Получаем конфигурацию одобрения
            config = self.get_approval_config(test_name, material_grade)
            if not config:
                logger.warning(f"Нет конфигурации одобрения для теста {test_name}")
                return True  # Если нет правил, считаем что одобрение не требуется
            
            # Создаем запросы на одобрение для каждого уровня
            for rule in config:
                if rule['is_required']:
                    # Проверяем, не существует ли уже такой запрос
                    cursor.execute("""
                        SELECT id FROM request_approvals
                        WHERE request_id = ? AND test_name = ? AND approval_level = ?
                    """, (request_id, test_name, rule['approval_level']))
                    
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO request_approvals
                            (request_id, test_name, approval_level, approver_login, approval_status)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            request_id, test_name, rule['approval_level'],
                            '', ApprovalStatus.PENDING.value
                        ))
            
            self.db_connection.commit()
            
            logger.info(f"Создан запрос на одобрение для заявки {request_id}, тест: {test_name}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка создания запроса на одобрение: {e}")
            return False
    
    def get_pending_approvals(self, user_login: str, user_roles: List[str]) -> List[Dict[str, Any]]:
        """
        Получение списка заявок, ожидающих одобрения пользователя.
        
        Args:
            user_login: Логин пользователя
            user_roles: Роли пользователя
            
        Returns:
            Список заявок для одобрения
        """
        try:
            cursor = self.db_connection.cursor()
            
            # Получаем заявки, которые может одобрить пользователь
            placeholders = ','.join(['?'] * len(user_roles))
            cursor.execute(f"""
                SELECT DISTINCT
                    ra.id, ra.request_id, ra.test_name, ra.approval_level,
                    lr.request_number, lr.created_at as request_created,
                    m.heat_num, g.grade,
                    ra.created_at as approval_created
                FROM request_approvals ra
                JOIN lab_requests lr ON ra.request_id = lr.id
                JOIN Materials m ON lr.material_id = m.id
                JOIN Grades g ON m.grade_id = g.id
                JOIN approval_config ac ON (
                    (ac.test_name = ra.test_name OR ac.test_name IS NULL)
                    AND ac.approval_level = ra.approval_level
                    AND ac.approver_role IN ({placeholders})
                )
                WHERE ra.approval_status = ?
                ORDER BY ra.created_at
            """, user_roles + [ApprovalStatus.PENDING.value])
            
            approvals = []
            for row in cursor.fetchall():
                approvals.append({
                    'id': row['id'],
                    'request_id': row['request_id'],
                    'request_number': row['request_number'],
                    'test_name': row['test_name'],
                    'approval_level': row['approval_level'],
                    'heat_num': row['heat_num'],
                    'grade': row['grade'],
                    'request_created': row['request_created'],
                    'approval_created': row['approval_created']
                })
            
            return approvals
            
        except Exception as e:
            logger.error(f"Ошибка получения заявок на одобрение: {e}")
            return []
    
    def approve_request(self, approval_id: int, user_login: str, 
                       comment: Optional[str] = None) -> bool:
        """
        Одобрение заявки.
        
        Args:
            approval_id: ID записи одобрения
            user_login: Логин пользователя
            comment: Комментарий к одобрению
            
        Returns:
            True если одобрение успешно
        """
        try:
            cursor = self.db_connection.cursor()
            
            # Получаем информацию о запросе на одобрение
            cursor.execute("""
                SELECT ra.*, lr.request_number
                FROM request_approvals ra
                JOIN lab_requests lr ON ra.request_id = lr.id
                WHERE ra.id = ?
            """, (approval_id,))
            
            row = cursor.fetchone()
            if not row:
                raise ValidationError("Запрос на одобрение не найден")
            
            if row['approval_status'] != ApprovalStatus.PENDING.value:
                raise ValidationError("Запрос уже обработан")
            
            # Обновляем статус одобрения
            cursor.execute("""
                UPDATE request_approvals
                SET approval_status = ?, approver_login = ?, 
                    approval_comment = ?, approved_at = ?
                WHERE id = ?
            """, (
                ApprovalStatus.APPROVED.value, user_login, comment,
                datetime.now().isoformat(), approval_id
            ))
            
            self.db_connection.commit()
            
            # Проверяем, все ли одобрения получены
            self._check_complete_approval(row['request_id'], row['test_name'])
            
            logger.info(f"Одобрена заявка {row['request_number']}, тест: {row['test_name']}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка одобрения заявки: {e}")
            return False
    
    def reject_request(self, approval_id: int, user_login: str, 
                      comment: str, required_changes: Optional[List[str]] = None) -> bool:
        """
        Отклонение заявки.
        
        Args:
            approval_id: ID записи одобрения
            user_login: Логин пользователя
            comment: Комментарий к отклонению
            required_changes: Список требуемых изменений
            
        Returns:
            True если отклонение успешно
        """
        try:
            if not comment.strip():
                raise ValidationError("Комментарий при отклонении обязателен")
            
            cursor = self.db_connection.cursor()
            
            # Получаем информацию о запросе на одобрение
            cursor.execute("""
                SELECT ra.*, lr.request_number
                FROM request_approvals ra
                JOIN lab_requests lr ON ra.request_id = lr.id
                WHERE ra.id = ?
            """, (approval_id,))
            
            row = cursor.fetchone()
            if not row:
                raise ValidationError("Запрос на одобрение не найден")
            
            if row['approval_status'] != ApprovalStatus.PENDING.value:
                raise ValidationError("Запрос уже обработан")
            
            # Обновляем статус одобрения
            required_changes_json = json.dumps(required_changes or [], ensure_ascii=False)
            
            cursor.execute("""
                UPDATE request_approvals
                SET approval_status = ?, approver_login = ?, 
                    approval_comment = ?, required_changes = ?, approved_at = ?
                WHERE id = ?
            """, (
                ApprovalStatus.REJECTED.value, user_login, comment,
                required_changes_json, datetime.now().isoformat(), approval_id
            ))
            
            self.db_connection.commit()
            
            logger.info(f"Отклонена заявка {row['request_number']}, тест: {row['test_name']}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка отклонения заявки: {e}")
            return False
    
    def return_for_revision(self, approval_id: int, user_login: str, 
                          comment: str, required_changes: List[str]) -> bool:
        """
        Возврат заявки на доработку.
        
        Args:
            approval_id: ID записи одобрения
            user_login: Логин пользователя
            comment: Комментарий к возврату
            required_changes: Список требуемых изменений
            
        Returns:
            True если возврат успешен
        """
        try:
            if not comment.strip():
                raise ValidationError("Комментарий при возврате обязателен")
            
            if not required_changes:
                raise ValidationError("Список требуемых изменений обязателен")
            
            cursor = self.db_connection.cursor()
            
            # Получаем информацию о запросе на одобрение
            cursor.execute("""
                SELECT ra.*, lr.request_number
                FROM request_approvals ra
                JOIN lab_requests lr ON ra.request_id = lr.id
                WHERE ra.id = ?
            """, (approval_id,))
            
            row = cursor.fetchone()
            if not row:
                raise ValidationError("Запрос на одобрение не найден")
            
            if row['approval_status'] != ApprovalStatus.PENDING.value:
                raise ValidationError("Запрос уже обработан")
            
            # Обновляем статус одобрения
            required_changes_json = json.dumps(required_changes, ensure_ascii=False)
            
            cursor.execute("""
                UPDATE request_approvals
                SET approval_status = ?, approver_login = ?, 
                    approval_comment = ?, required_changes = ?, approved_at = ?
                WHERE id = ?
            """, (
                ApprovalStatus.RETURNED.value, user_login, comment,
                required_changes_json, datetime.now().isoformat(), approval_id
            ))
            
            self.db_connection.commit()
            
            logger.info(f"Возвращена на доработку заявка {row['request_number']}, тест: {row['test_name']}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка возврата заявки: {e}")
            return False
    
    def get_approval_history(self, request_id: int, 
                           test_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение истории одобрений заявки.
        
        Args:
            request_id: ID заявки
            test_name: Название теста (если None - вся заявка)
            
        Returns:
            История одобрений
        """
        try:
            cursor = self.db_connection.cursor()
            
            if test_name:
                cursor.execute("""
                    SELECT ra.*, ac.approver_role
                    FROM request_approvals ra
                    LEFT JOIN approval_config ac ON (
                        (ac.test_name = ra.test_name OR ac.test_name IS NULL)
                        AND ac.approval_level = ra.approval_level
                    )
                    WHERE ra.request_id = ? AND ra.test_name = ?
                    ORDER BY ra.approval_level, ra.created_at
                """, (request_id, test_name))
            else:
                cursor.execute("""
                    SELECT ra.*, ac.approver_role
                    FROM request_approvals ra
                    LEFT JOIN approval_config ac ON (
                        (ac.test_name = ra.test_name OR ac.test_name IS NULL)
                        AND ac.approval_level = ra.approval_level
                    )
                    WHERE ra.request_id = ?
                    ORDER BY ra.test_name, ra.approval_level, ra.created_at
                """, (request_id,))
            
            history = []
            for row in cursor.fetchall():
                required_changes = []
                if row['required_changes']:
                    try:
                        required_changes = json.loads(row['required_changes'])
                    except json.JSONDecodeError:
                        pass
                
                history.append({
                    'id': row['id'],
                    'test_name': row['test_name'],
                    'approval_level': row['approval_level'],
                    'approver_role': row['approver_role'],
                    'approver_login': row['approver_login'],
                    'approval_status': row['approval_status'],
                    'approval_comment': row['approval_comment'],
                    'required_changes': required_changes,
                    'created_at': row['created_at'],
                    'approved_at': row['approved_at']
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Ошибка получения истории одобрений: {e}")
            return []
    
    def get_approval_status(self, request_id: int, 
                          test_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение статуса одобрения заявки.
        
        Args:
            request_id: ID заявки
            test_name: Название теста (если None - вся заявка)
            
        Returns:
            Статус одобрения
        """
        try:
            cursor = self.db_connection.cursor()
            
            if test_name:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN approval_status = 'approved' THEN 1 END) as approved,
                        COUNT(CASE WHEN approval_status = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN approval_status = 'rejected' THEN 1 END) as rejected,
                        COUNT(CASE WHEN approval_status = 'returned' THEN 1 END) as returned
                    FROM request_approvals
                    WHERE request_id = ? AND test_name = ?
                """, (request_id, test_name))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN approval_status = 'approved' THEN 1 END) as approved,
                        COUNT(CASE WHEN approval_status = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN approval_status = 'rejected' THEN 1 END) as rejected,
                        COUNT(CASE WHEN approval_status = 'returned' THEN 1 END) as returned
                    FROM request_approvals
                    WHERE request_id = ?
                """, (request_id,))
            
            row = cursor.fetchone()
            
            if row['total'] == 0:
                overall_status = 'not_required'
            elif row['rejected'] > 0:
                overall_status = 'rejected'
            elif row['returned'] > 0:
                overall_status = 'returned'
            elif row['pending'] > 0:
                overall_status = 'pending'
            elif row['approved'] == row['total']:
                overall_status = 'approved'
            else:
                overall_status = 'partial'
            
            return {
                'total': row['total'],
                'approved': row['approved'],
                'pending': row['pending'],
                'rejected': row['rejected'],
                'returned': row['returned'],
                'overall_status': overall_status
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса одобрения: {e}")
            return {
                'total': 0,
                'approved': 0,
                'pending': 0,
                'rejected': 0,
                'returned': 0,
                'overall_status': 'error'
            }
    
    def reset_approval_after_changes(self, request_id: int, 
                                   test_name: Optional[str] = None) -> bool:
        """
        Сброс одобрений после изменения результатов.
        
        Args:
            request_id: ID заявки
            test_name: Название теста (если None - вся заявка)
            
        Returns:
            True если сброс успешен
        """
        try:
            cursor = self.db_connection.cursor()
            
            if test_name:
                cursor.execute("""
                    UPDATE request_approvals
                    SET approval_status = ?, approver_login = '', 
                        approval_comment = NULL, approved_at = NULL
                    WHERE request_id = ? AND test_name = ? 
                    AND approval_status IN ('approved', 'rejected')
                """, (ApprovalStatus.PENDING.value, request_id, test_name))
            else:
                cursor.execute("""
                    UPDATE request_approvals
                    SET approval_status = ?, approver_login = '', 
                        approval_comment = NULL, approved_at = NULL
                    WHERE request_id = ? 
                    AND approval_status IN ('approved', 'rejected')
                """, (ApprovalStatus.PENDING.value, request_id))
            
            self.db_connection.commit()
            
            logger.info(f"Сброшены одобрения для заявки {request_id}, тест: {test_name}")
            return True
            
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка сброса одобрений: {e}")
            return False
    
    def _check_complete_approval(self, request_id: int, test_name: Optional[str]):
        """Проверка завершения процесса одобрения."""
        try:
            status = self.get_approval_status(request_id, test_name)
            
            if status['overall_status'] == 'approved':
                # Все одобрения получены, можно обновить статус заявки
                cursor = self.db_connection.cursor()
                
                if test_name:
                    # Обновляем статус конкретного теста
                    logger.info(f"Тест {test_name} заявки {request_id} полностью одобрен")
                else:
                    # Обновляем статус всей заявки
                    cursor.execute("""
                        UPDATE lab_requests 
                        SET status = 'approved' 
                        WHERE id = ?
                    """, (request_id,))
                    
                    self.db_connection.commit()
                    logger.info(f"Заявка {request_id} полностью одобрена")
                    
        except Exception as e:
            logger.error(f"Ошибка проверки завершения одобрения: {e}")
    
    def get_approvers_for_role(self, role: str) -> List[str]:
        """
        Получение списка пользователей с определенной ролью.
        
        Args:
            role: Название роли
            
        Returns:
            Список логинов пользователей
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT DISTINCT u.login
                FROM Users u
                JOIN UserRoles ur ON u.id = ur.user_id
                JOIN Roles r ON ur.role_id = r.id
                WHERE r.name = ?
            """, (role,))
            
            return [row['login'] for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователей для роли {role}: {e}")
            return [] 