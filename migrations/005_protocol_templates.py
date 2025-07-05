"""
Миграция для создания таблицы protocol_templates.

Добавляет систему шаблонов протоколов с поддержкой Jinja2.
"""

import sqlite3
from typing import Dict, Any


def up(connection: sqlite3.Connection) -> None:
    """
    Применение миграции.
    
    Создает:
    1. Таблицу protocol_templates для хранения шаблонов
    2. Индексы для оптимизации поиска
    3. Базовые шаблоны протоколов
    """
    cursor = connection.cursor()
    
    # Создаем таблицу protocol_templates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS protocol_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            template_content TEXT NOT NULL,
            variables_json TEXT NOT NULL DEFAULT '[]',
            formulas_json TEXT NOT NULL DEFAULT '[]',
            output_format TEXT NOT NULL DEFAULT 'pdf',
            created_by TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            updated_at DATETIME,
            version INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            is_default BOOLEAN DEFAULT 0
        )
    """)
    
    # Создаем индексы
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_protocol_templates_category 
        ON protocol_templates(category)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_protocol_templates_active 
        ON protocol_templates(is_active)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_protocol_templates_name 
        ON protocol_templates(name)
    """)
    
    # Создаем таблицу для истории изменений шаблонов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS protocol_template_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            template_content TEXT NOT NULL,
            variables_json TEXT NOT NULL,
            formulas_json TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            change_comment TEXT,
            FOREIGN KEY (template_id) REFERENCES protocol_templates(id)
        )
    """)
    
    # Создаем таблицу для переменных шаблонов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS template_variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            data_type TEXT NOT NULL DEFAULT 'text',
            default_value TEXT,
            description TEXT,
            validation_rules TEXT,
            category TEXT DEFAULT 'custom',
            is_system BOOLEAN DEFAULT 0
        )
    """)
    
    # Вставляем базовые переменные системы
    system_variables = [
        ('request_number', 'Номер заявки', 'text', '', 'Номер лабораторной заявки', '', 'system', 1),
        ('creation_date', 'Дата создания', 'date', '', 'Дата создания заявки', '', 'system', 1),
        ('material_grade', 'Марка материала', 'text', '', 'Марка испытываемого материала', '', 'material', 1),
        ('material_size', 'Размер', 'text', '', 'Размер проката', '', 'material', 1),
        ('rolling_type', 'Вид проката', 'text', '', 'Тип проката', '', 'material', 1),
        ('heat_number', 'Номер плавки', 'text', '', 'Номер плавки материала', '', 'material', 1),
        ('cert_number', 'Номер сертификата', 'text', '', 'Номер сертификата качества', '', 'material', 1),
        ('test_scenario', 'Сценарий испытаний', 'text', '', 'Выбранный сценарий испытаний', '', 'testing', 1),
        ('test_results', 'Результаты испытаний', 'json', '[]', 'Результаты проведенных испытаний', '', 'testing', 1),
        ('lab_status', 'Статус заявки', 'text', '', 'Текущий статус лабораторной заявки', '', 'system', 1),
        ('operator_name', 'Оператор', 'text', '', 'Имя оператора, выполняющего испытания', '', 'system', 1),
        ('test_date', 'Дата испытаний', 'date', '', 'Дата проведения испытаний', '', 'testing', 1),
        ('report_date', 'Дата отчета', 'date', '', 'Дата формирования отчета', '', 'system', 1),
        ('temperature', 'Температура испытаний', 'number', '20', 'Температура проведения испытаний (°C)', '', 'testing', 1),
        ('humidity', 'Влажность', 'number', '50', 'Относительная влажность (%)', '', 'testing', 1)
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO template_variables 
        (name, display_name, data_type, default_value, description, validation_rules, category, is_system)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, system_variables)
    
    # Создаем базовые шаблоны
    base_templates = [
        {
            'name': 'Протокол механических испытаний',
            'description': 'Стандартный протокол для механических испытаний металлопроката',
            'category': 'mechanical',
            'template_content': """# ПРОТОКОЛ МЕХАНИЧЕСКИХ ИСПЫТАНИЙ

**Номер заявки:** {{ request_number }}
**Дата:** {{ creation_date }}

## Сведения о материале
- **Марка материала:** {{ material_grade }}
- **Вид проката:** {{ rolling_type }}
- **Размер:** {{ material_size }}
- **Номер плавки:** {{ heat_number }}
- **Номер сертификата:** {{ cert_number }}

## Условия испытаний
- **Температура:** {{ temperature }}°C
- **Влажность:** {{ humidity }}%
- **Дата испытаний:** {{ test_date }}

## Результаты испытаний
{% for result in test_results %}
**{{ result.name }}:** {{ result.result }} {{ result.unit|default('') }}
{% endfor %}

## Заключение
{% if lab_status == 'ППСД пройден' %}
✅ **МАТЕРИАЛ СООТВЕТСТВУЕТ ТРЕБОВАНИЯМ**
{% elif lab_status == 'Брак материала' %}
❌ **МАТЕРИАЛ НЕ СООТВЕТСТВУЕТ ТРЕБОВАНИЯМ**
{% else %}
⏳ **ИСПЫТАНИЯ В ПРОЦЕССЕ**
{% endif %}

---
**Оператор:** {{ operator_name }}
**Дата отчета:** {{ report_date }}
""",
            'variables_json': '["request_number", "creation_date", "material_grade", "rolling_type", "material_size", "heat_number", "cert_number", "temperature", "humidity", "test_date", "test_results", "lab_status", "operator_name", "report_date"]',
            'formulas_json': '[]',
            'output_format': 'pdf',
            'created_by': 'system',
            'is_default': 1
        },
        {
            'name': 'Краткий протокол испытаний',
            'description': 'Упрощенный протокол для быстрого оформления результатов',
            'category': 'simple',
            'template_content': """# ПРОТОКОЛ ИСПЫТАНИЙ №{{ request_number }}

**Материал:** {{ material_grade }} ({{ rolling_type }} {{ material_size }})
**Плавка:** {{ heat_number }}
**Дата:** {{ test_date }}

## Результаты:
{% for result in test_results %}
- {{ result.name }}: **{{ result.result }}** {{ result.unit|default('') }}
{% endfor %}

**Статус:** {{ lab_status }}
**Оператор:** {{ operator_name }}
""",
            'variables_json': '["request_number", "material_grade", "rolling_type", "material_size", "heat_number", "test_date", "test_results", "lab_status", "operator_name"]',
            'formulas_json': '[]',
            'output_format': 'pdf',
            'created_by': 'system',
            'is_default': 0
        },
        {
            'name': 'Протокол с расчетами',
            'description': 'Протокол с автоматическими расчетами и формулами',
            'category': 'calculated',
            'template_content': """# ПРОТОКОЛ ИСПЫТАНИЙ С РАСЧЕТАМИ

**Заявка:** {{ request_number }} от {{ creation_date }}

## Материал
{{ material_grade }} {{ rolling_type }} {{ material_size }}

## Результаты и расчеты
{% for result in test_results %}
**{{ result.name }}:** {{ result.result }} {{ result.unit|default('') }}
{% endfor %}

{% if calculated_values %}
## Расчетные значения
{% for calc in calculated_values %}
**{{ calc.name }}:** {{ calc.value }} {{ calc.unit|default('') }}
{% endfor %}
{% endif %}

## Заключение
Испытания выполнены в соответствии с {{ test_scenario }}.
Результат: **{{ lab_status }}**

*Протокол сгенерирован {{ report_date }}*
""",
            'variables_json': '["request_number", "creation_date", "material_grade", "rolling_type", "material_size", "test_results", "calculated_values", "test_scenario", "lab_status", "report_date"]',
            'formulas_json': '[{"name": "relative_elongation", "formula": "(final_length - initial_length) / initial_length * 100", "description": "Относительное удлинение, %"}]',
            'output_format': 'pdf',
            'created_by': 'system',
            'is_default': 0
        }
    ]
    
    for template in base_templates:
        cursor.execute("""
            INSERT OR IGNORE INTO protocol_templates 
            (name, description, category, template_content, variables_json, formulas_json, 
             output_format, created_by, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template['name'], template['description'], template['category'],
            template['template_content'], template['variables_json'], 
            template['formulas_json'], template['output_format'],
            template['created_by'], template['is_default']
        ))
    
    connection.commit()
    print("✅ Миграция 005: Создана система шаблонов протоколов")


def down(connection: sqlite3.Connection) -> None:
    """
    Откат миграции.
    
    Удаляет таблицы связанные с шаблонами протоколов.
    """
    cursor = connection.cursor()
    
    # Удаляем таблицы в правильном порядке (с учетом внешних ключей)
    cursor.execute("DROP TABLE IF EXISTS protocol_template_history")
    cursor.execute("DROP TABLE IF EXISTS template_variables") 
    cursor.execute("DROP TABLE IF EXISTS protocol_templates")
    
    connection.commit()
    print("✅ Откат миграции 005: Удалена система шаблонов протоколов")


def get_migration_info() -> Dict[str, Any]:
    """
    Информация о миграции.
    
    Returns:
        Словарь с метаданными миграции
    """
    return {
        'version': '005',
        'name': 'protocol_templates',
        'description': 'Создание системы шаблонов протоколов с поддержкой Jinja2',
        'author': 'system',
        'created_at': '2024-01-05',
        'dependencies': ['004_user_sessions'],
        'tables_created': [
            'protocol_templates',
            'protocol_template_history', 
            'template_variables'
        ],
        'indexes_created': [
            'idx_protocol_templates_category',
            'idx_protocol_templates_active',
            'idx_protocol_templates_name'
        ]
    } 