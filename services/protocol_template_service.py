"""
Сервис для работы с шаблонами протоколов лаборатории.

Предоставляет функциональность для:
- Создания и редактирования шаблонов
- Генерации протоколов на основе шаблонов
- Работы с переменными и формулами
- Превью протоколов
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import math

from jinja2 import Environment, BaseLoader, Template, TemplateError, select_autoescape, StrictUndefined
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from utils.logger import get_logger
from utils.exceptions import ValidationError, BusinessLogicError

logger = get_logger(__name__)


class ProtocolTemplateService:
    """
    Сервис для работы с шаблонами протоколов.
    """
    
    def __init__(self, db_connection, docs_root: str = ""):
        """
        Инициализация сервиса.
        
        Args:
            db_connection: Подключение к базе данных
            docs_root: Корневая папка для документов
        """
        self.db_connection = db_connection
        self.docs_root = Path(docs_root) if docs_root else Path.cwd()
        self.jinja_env = self._setup_jinja_environment()
        
    def _setup_jinja_environment(self) -> Environment:
        """
        Настройка окружения Jinja2.
        
        Returns:
            Настроенное окружение Jinja2
        """
        env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined  # Строгая обработка неопределенных переменных
        )
        
        # Добавляем пользовательские фильтры
        env.filters.update({
            'format_date': self._format_date_filter,
            'format_number': self._format_number_filter,
            'safe_divide': self._safe_divide_filter,
            'calculate': self._calculate_filter,
            'format_result': self._format_result_filter
        })
        
        # Добавляем пользовательские функции
        env.globals.update({
            'now': datetime.now,
            'today': datetime.now().date,
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'calculate_formula': self._calculate_formula
        })
        
        return env
    
    def _format_date_filter(self, value, format_str='%d.%m.%Y'):
        """Фильтр для форматирования дат."""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                return value
        return value.strftime(format_str) if value else ''
    
    def _format_number_filter(self, value, decimals=2):
        """Фильтр для форматирования чисел."""
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return str(value)
    
    def _safe_divide_filter(self, numerator, denominator, default=0):
        """Безопасное деление с обработкой деления на ноль."""
        try:
            return float(numerator) / float(denominator)
        except (ValueError, TypeError, ZeroDivisionError):
            return default
    
    def _calculate_filter(self, formula: str, variables: Dict[str, Any]):
        """Фильтр для выполнения вычислений."""
        return self._calculate_formula(formula, variables)
    
    def _format_result_filter(self, result: Dict[str, Any]):
        """Форматирование результата испытания."""
        name = result.get('name', '')
        value = result.get('result', '')
        unit = result.get('unit', '')
        return f"{name}: {value} {unit}".strip()
    
    def _calculate_formula(self, formula: str, variables: Dict[str, Any]) -> Any:
        """
        Безопасное вычисление формулы.
        
        Args:
            formula: Формула для вычисления
            variables: Переменные для подстановки
            
        Returns:
            Результат вычисления
        """
        try:
            # Разрешенные функции для безопасности
            safe_dict = {
                'abs': abs, 'round': round, 'min': min, 'max': max,
                'sum': sum, 'len': len, 'pow': pow, 'sqrt': math.sqrt,
                'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
                'log': math.log, 'log10': math.log10, 'exp': math.exp,
                'pi': math.pi, 'e': math.e
            }
            safe_dict.update(variables)
            
            # Проверяем формулу на безопасность
            if not self._is_safe_formula(formula):
                raise ValidationError("Небезопасная формула")
            
            return eval(formula, {"__builtins__": {}}, safe_dict)
            
        except Exception as e:
            logger.warning(f"Ошибка вычисления формулы '{formula}': {e}")
            return 0
    
    def _is_safe_formula(self, formula: str) -> bool:
        """
        Проверка формулы на безопасность.
        
        Args:
            formula: Формула для проверки
            
        Returns:
            True если формула безопасна
        """
        # Запрещенные ключевые слова и функции
        forbidden = [
            'import', 'exec', 'eval', 'open', 'file', 'input', 'raw_input',
            '__', 'getattr', 'setattr', 'delattr', 'globals', 'locals',
            'vars', 'dir', 'help', 'quit', 'exit', 'compile', 'reload'
        ]
        
        formula_lower = formula.lower()
        return not any(word in formula_lower for word in forbidden)
    
    def get_all_templates(self, category: Optional[str] = None, 
                         active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Получение списка всех шаблонов.
        
        Args:
            category: Фильтр по категории
            active_only: Только активные шаблоны
            
        Returns:
            Список шаблонов
        """
        try:
            query = """
                SELECT id, name, description, category, output_format,
                       created_by, created_at, updated_at, version,
                       is_active, is_default
                FROM protocol_templates
                WHERE 1=1
            """
            params = []
            
            if active_only:
                query += " AND is_active = ?"
                params.append(1)
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            query += " ORDER BY is_default DESC, name ASC"
            
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            
            templates = []
            for row in cursor.fetchall():
                templates.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'category': row['category'],
                    'output_format': row['output_format'],
                    'created_by': row['created_by'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'version': row['version'],
                    'is_active': bool(row['is_active']),
                    'is_default': bool(row['is_default'])
                })
            
            logger.info(f"Получено {len(templates)} шаблонов протоколов")
            return templates
            
        except Exception as e:
            logger.error(f"Ошибка получения шаблонов: {e}")
            raise BusinessLogicError(
                message="Ошибка получения списка шаблонов",
                original_error=e
            )
    
    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение шаблона по ID.
        
        Args:
            template_id: ID шаблона
            
        Returns:
            Данные шаблона или None
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT * FROM protocol_templates WHERE id = ?
            """, (template_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'category': row['category'],
                'template_content': row['template_content'],
                'variables': json.loads(row['variables_json']),
                'formulas': json.loads(row['formulas_json']),
                'output_format': row['output_format'],
                'created_by': row['created_by'],
                'created_at': row['created_at'],
                'updated_by': row['updated_by'],
                'updated_at': row['updated_at'],
                'version': row['version'],
                'is_active': bool(row['is_active']),
                'is_default': bool(row['is_default'])
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения шаблона {template_id}: {e}")
            return None
    
    def create_template(self, template_data: Dict[str, Any], user_login: str) -> int:
        """
        Создание нового шаблона.
        
        Args:
            template_data: Данные шаблона
            user_login: Логин пользователя
            
        Returns:
            ID созданного шаблона
        """
        try:
            # Валидация данных
            self._validate_template_data(template_data)
            
            # Проверка синтаксиса шаблона
            self._validate_template_syntax(template_data['template_content'])
            
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO protocol_templates 
                (name, description, category, template_content, variables_json, 
                 formulas_json, output_format, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template_data['name'],
                template_data.get('description', ''),
                template_data.get('category', 'general'),
                template_data['template_content'],
                json.dumps(template_data.get('variables', []), ensure_ascii=False),
                json.dumps(template_data.get('formulas', []), ensure_ascii=False),
                template_data.get('output_format', 'pdf'),
                user_login
            ))
            
            template_id = cursor.lastrowid
            self.db_connection.commit()
            
            logger.info(f"Создан шаблон протокола {template_id} пользователем {user_login}")
            return template_id
            
        except ValidationError:
            # Перебрасываем ValidationError без изменений
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка создания шаблона: {e}")
            raise BusinessLogicError(
                message="Ошибка создания шаблона протокола",
                original_error=e
            )
    
    def update_template(self, template_id: int, template_data: Dict[str, Any], 
                       user_login: str) -> bool:
        """
        Обновление шаблона.
        
        Args:
            template_id: ID шаблона
            template_data: Новые данные
            user_login: Логин пользователя
            
        Returns:
            True если обновление прошло успешно
        """
        try:
            # Валидация данных
            self._validate_template_data(template_data)
            self._validate_template_syntax(template_data['template_content'])
            
            # Сохраняем текущую версию в историю
            current_template = self.get_template_by_id(template_id)
            if current_template:
                self._save_template_history(template_id, current_template, user_login)
            
            cursor = self.db_connection.cursor()
            cursor.execute("""
                UPDATE protocol_templates 
                SET name = ?, description = ?, category = ?, template_content = ?,
                    variables_json = ?, formulas_json = ?, output_format = ?,
                    updated_by = ?, updated_at = CURRENT_TIMESTAMP, version = version + 1
                WHERE id = ?
            """, (
                template_data['name'],
                template_data.get('description', ''),
                template_data.get('category', 'general'),
                template_data['template_content'],
                json.dumps(template_data.get('variables', []), ensure_ascii=False),
                json.dumps(template_data.get('formulas', []), ensure_ascii=False),
                template_data.get('output_format', 'pdf'),
                user_login,
                template_id
            ))
            
            self.db_connection.commit()
            
            logger.info(f"Обновлен шаблон {template_id} пользователем {user_login}")
            return cursor.rowcount > 0
            
        except ValidationError:
            # Перебрасываем ValidationError без изменений
            raise
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка обновления шаблона {template_id}: {e}")
            raise BusinessLogicError(
                message="Ошибка обновления шаблона",
                original_error=e
            )
    
    def _save_template_history(self, template_id: int, template_data: Dict[str, Any], 
                              user_login: str, comment: str = ""):
        """Сохранение версии шаблона в историю."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO protocol_template_history 
                (template_id, template_content, variables_json, formulas_json, 
                 changed_by, change_comment)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                template_id,
                template_data['template_content'],
                json.dumps(template_data.get('variables', []), ensure_ascii=False),
                json.dumps(template_data.get('formulas', []), ensure_ascii=False),
                user_login,
                comment
            ))
            
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории шаблона {template_id}: {e}")
    
    def _validate_template_data(self, template_data: Dict[str, Any]) -> None:
        """
        Валидация данных шаблона.
        
        Args:
            template_data: Данные для валидации
            
        Raises:
            ValidationError: При ошибках валидации
        """
        required_fields = ['name', 'template_content']
        
        for field in required_fields:
            if not template_data.get(field):
                raise ValidationError(f"Поле '{field}' обязательно для заполнения")
        
        # Проверка уникальности имени
        if self._is_template_name_exists(template_data['name'], 
                                       template_data.get('id')):
            raise ValidationError("Шаблон с таким именем уже существует")
    
    def _is_template_name_exists(self, name: str, exclude_id: Optional[int] = None) -> bool:
        """Проверка существования шаблона с таким именем."""
        cursor = self.db_connection.cursor()
        query = "SELECT id FROM protocol_templates WHERE name = ?"
        params = [name]
        
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)
        
        cursor.execute(query, params)
        return cursor.fetchone() is not None
    
    def _validate_template_syntax(self, template_content: str) -> None:
        """
        Валидация синтаксиса Jinja2 шаблона.
        
        Args:
            template_content: Содержимое шаблона
            
        Raises:
            ValidationError: При ошибках синтаксиса
        """
        try:
            self.jinja_env.from_string(template_content)
        except TemplateSyntaxError as e:
            raise ValidationError(f"Ошибка синтаксиса шаблона: {e}")
        except Exception as e:
            raise ValidationError(f"Ошибка валидации шаблона: {e}")
    
    def generate_protocol(self, template_id: int, context_data: Dict[str, Any], 
                         calculate_formulas: bool = True) -> str:
        """
        Генерация протокола на основе шаблона.
        
        Args:
            template_id: ID шаблона
            context_data: Данные для подстановки
            calculate_formulas: Выполнять ли расчет формул
            
        Returns:
            Сгенерированный текст протокола
        """
        try:
            template_data = self.get_template_by_id(template_id)
            if not template_data:
                raise ValidationError(f"Шаблон {template_id} не найден")
            
            # Подготавливаем контекст
            context = self._prepare_context(template_data, context_data, calculate_formulas)
            
            # Создаем и рендерим шаблон
            template = self.jinja_env.from_string(template_data['template_content'])
            rendered = template.render(**context)
            
            logger.info(f"Сгенерирован протокол по шаблону {template_id}")
            return rendered
            
        except ValidationError:
            # Перебрасываем ValidationError без изменений
            raise
        except Exception as e:
            logger.error(f"Ошибка генерации протокола: {e}")
            raise BusinessLogicError(
                message="Ошибка генерации протокола",
                original_error=e
            )
    
    def _prepare_context(self, template_data: Dict[str, Any], 
                        context_data: Dict[str, Any], 
                        calculate_formulas: bool) -> Dict[str, Any]:
        """
        Подготовка контекста для рендеринга шаблона.
        
        Args:
            template_data: Данные шаблона
            context_data: Исходные данные
            calculate_formulas: Выполнять ли расчеты
            
        Returns:
            Подготовленный контекст
        """
        context = dict(context_data)
        
        # Добавляем системные переменные
        context.update({
            'report_date': datetime.now().strftime('%d.%m.%Y'),
            'report_time': datetime.now().strftime('%H:%M'),
            'template_name': template_data['name'],
            'template_version': template_data.get('version', 1)  # Безопасный доступ к version
        })
        
        # Выполняем расчеты формул если нужно
        if calculate_formulas and template_data.get('formulas'):
            calculated_values = []
            for formula_def in template_data['formulas']:
                try:
                    result = self._calculate_formula(
                        formula_def['formula'], context
                    )
                    calculated_values.append({
                        'name': formula_def['name'],
                        'value': result,
                        'formula': formula_def['formula'],
                        'description': formula_def.get('description', '')
                    })
                except Exception as e:
                    logger.warning(f"Ошибка расчета формулы {formula_def['name']}: {e}")
            
            context['calculated_values'] = calculated_values
        
        return context
    
    def get_template_variables(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка доступных переменных для шаблонов.
        
        Args:
            category: Фильтр по категории
            
        Returns:
            Список переменных
        """
        try:
            query = """
                SELECT name, display_name, data_type, default_value,
                       description, category, is_system
                FROM template_variables
                WHERE 1=1
            """
            params = []
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            query += " ORDER BY is_system DESC, category, display_name"
            
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            
            variables = []
            for row in cursor.fetchall():
                variables.append({
                    'name': row['name'],
                    'display_name': row['display_name'],
                    'data_type': row['data_type'],
                    'default_value': row['default_value'],
                    'description': row['description'],
                    'category': row['category'],
                    'is_system': bool(row['is_system'])
                })
            
            return variables
            
        except Exception as e:
            logger.error(f"Ошибка получения переменных: {e}")
            return []
    
    def preview_protocol(self, template_content: str, 
                        context_data: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        Превью протокола без сохранения шаблона.
        
        Args:
            template_content: Содержимое шаблона
            context_data: Данные для подстановки
            
        Returns:
            Кортеж (результат, список ошибок)
        """
        errors = []
        result = ""
        
        try:
            # Используем основное окружение для превью чтобы ловить UndefinedError
            template = self.jinja_env.from_string(template_content)
            
            # Рендерим с обработкой ошибок
            result = template.render(**context_data)
            
        except TemplateSyntaxError as e:
            errors.append(f"Синтаксическая ошибка: {e}")
        except UndefinedError as e:
            errors.append(f"Неопределенная переменная: {e}")
        except Exception as e:
            errors.append(f"Ошибка рендеринга: {e}")
        
        return result, errors
    
    def delete_template(self, template_id: int, user_login: str) -> bool:
        """
        Удаление шаблона (мягкое удаление).
        
        Args:
            template_id: ID шаблона
            user_login: Логин пользователя
            
        Returns:
            True если удаление прошло успешно
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                UPDATE protocol_templates 
                SET is_active = 0, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_login, template_id))
            
            self.db_connection.commit()
            
            logger.info(f"Деактивирован шаблон {template_id} пользователем {user_login}")
            return cursor.rowcount > 0
            
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Ошибка удаления шаблона {template_id}: {e}")
            return False 