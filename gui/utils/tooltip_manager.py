"""
Система управления подсказками (Tooltips) для улучшения пользовательского опыта.

Особенности:
- Интеллектуальные подсказки с контекстом
- Богатые HTML tooltips с иконками
- Адаптивное позиционирование
- Задержки и анимации
- Мультиязычная поддержка
"""

import os
import json
from typing import Dict, Any, Optional, List, Callable
from PyQt5.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, 
    QApplication, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QPixmap, QPainter
from utils.logger import get_logger

logger = get_logger('gui.tooltip_manager')


class RichTooltip(QFrame):
    """
    Богатая подсказка с поддержкой HTML, иконок и анимаций.
    """
    
    def __init__(self, text: str, icon: str = None, parent: QWidget = None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setObjectName("RichTooltip")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self._setup_ui(text, icon)
        self._setup_animations()
        self._apply_styles()
    
    def _setup_ui(self, text: str, icon: str):
        """Настройка интерфейса подсказки."""
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Иконка (опционально)
        if icon:
            icon_label = QLabel()
            icon_label.setFixedSize(16, 16)
            
            # Загружаем иконку
            icon_path = f"resources/icons/{icon}"
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(pixmap)
            else:
                icon_label.setText("ℹ️")
                icon_label.setAlignment(Qt.AlignCenter)
            
            layout.addWidget(icon_label)
        
        # Текст подсказки
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setFont(QFont("Segoe UI", 9))
        text_label.setTextFormat(Qt.RichText)
        layout.addWidget(text_label)
        
        self.setLayout(layout)
    
    def _setup_animations(self):
        """Настройка анимаций."""
        # Анимация появления
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Начальное состояние
        self.setWindowOpacity(0.0)
    
    def _apply_styles(self):
        """Применение стилей."""
        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)
        
        # Стили CSS
        self.setStyleSheet("""
            QFrame#RichTooltip {
                background-color: rgba(42, 42, 42, 240);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 8px;
                color: white;
            }
            
            QLabel {
                color: white;
                background: transparent;
                border: none;
            }
        """)
    
    def show_animated(self):
        """Показывает подсказку с анимацией."""
        self.show()
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
    
    def hide_animated(self, callback: Callable = None):
        """Скрывает подсказку с анимацией."""
        self.fade_animation.finished.disconnect()
        if callback:
            self.fade_animation.finished.connect(callback)
        
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()


class TooltipManager:
    """
    Менеджер системы подсказок.
    
    Особенности:
    - Автоматическое управление подсказками
    - Контекстные подсказки на основе роли пользователя
    - Богатые HTML tooltips
    - Интеллектуальное позиционирование
    - Кэширование и оптимизация
    """
    
    def __init__(self, language: str = "ru"):
        self.language = language
        self.tooltips_config = {}
        self.active_tooltip: Optional[RichTooltip] = None
        self.show_timer = QTimer()
        self.hide_timer = QTimer()
        self.current_widget: Optional[QWidget] = None
        
        # Настройка таймеров
        self.show_timer.setSingleShot(True)
        self.show_timer.timeout.connect(self._show_tooltip)
        
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_tooltip)
        
        # Загружаем конфигурацию
        self._load_tooltips_config()
        
        logger.info(f"TooltipManager инициализирован для языка: {language}")
    
    def _load_tooltips_config(self):
        """Загружает конфигурацию подсказок."""
        config_path = f"resources/tooltips/tooltips_{self.language}.json"
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.tooltips_config = json.load(f)
                logger.debug(f"Загружена конфигурация подсказок: {len(self.tooltips_config)} элементов")
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации подсказок: {e}")
                self._create_default_config()
        else:
            logger.warning(f"Файл конфигурации {config_path} не найден, создаю базовый")
            self._create_default_config()
    
    def _create_default_config(self):
        """Создает базовую конфигурацию подсказок."""
        self.tooltips_config = {
            "buttons": {
                "add": {
                    "text": "Добавить новый элемент",
                    "icon": "add_light.svg",
                    "hotkey": "Ctrl+N"
                },
                "edit": {
                    "text": "Редактировать выбранный элемент",
                    "icon": "edit_light.svg", 
                    "hotkey": "Ctrl+E"
                },
                "delete": {
                    "text": "Удалить выбранный элемент",
                    "icon": "delete_light.svg",
                    "hotkey": "Delete",
                    "warning": "Будьте осторожны! Это действие нельзя отменить."
                },
                "refresh": {
                    "text": "Обновить список данных",
                    "icon": "refresh_light.svg",
                    "hotkey": "F5"
                },
                "search": {
                    "text": "Поиск по данным",
                    "icon": "search_light.svg",
                    "hotkey": "Ctrl+F"
                },
                "theme_toggle": {
                    "text": "Переключить тему интерфейса",
                    "icon": "theme_toggle_light.svg",
                    "hotkey": "Ctrl+T"
                }
            },
            "fields": {
                "login": {
                    "text": "Введите ваш логин для входа в систему",
                    "example": "Пример: admin"
                },
                "password": {
                    "text": "Введите пароль для авторизации",
                    "security": "Пароль должен содержать минимум 6 символов"
                },
                "material_name": {
                    "text": "Название материала или изделия",
                    "example": "Пример: Лист стальной"
                },
                "supplier": {
                    "text": "Выберите поставщика из списка",
                    "autocomplete": True
                }
            },
            "tables": {
                "materials": {
                    "text": "Таблица материалов. Используйте правую кнопку мыши для контекстного меню",
                    "features": ["Сортировка по колонкам", "Фильтрация", "Экспорт данных"]
                }
            },
            "menu": {
                "file": {
                    "text": "Операции с файлами и данными"
                },
                "edit": {
                    "text": "Редактирование и настройки"
                },
                "view": {
                    "text": "Настройки отображения"
                },
                "help": {
                    "text": "Справка и информация о программе"
                }
            }
        }
    
    def register_widget(self, widget: QWidget, tooltip_id: str, 
                       category: str = "buttons", custom_text: str = None,
                       user_role: str = None):
        """
        Регистрирует виджет для отображения подсказок.
        
        Args:
            widget: Виджет для добавления подсказки
            tooltip_id: ID подсказки в конфигурации
            category: Категория подсказки
            custom_text: Пользовательский текст (переопределяет конфигурацию)
            user_role: Роль пользователя для контекстных подсказок
        """
        if not widget:
            return
        
        # Получаем конфигурацию подсказки
        tooltip_config = self.tooltips_config.get(category, {}).get(tooltip_id, {})
        
        if not tooltip_config and not custom_text:
            logger.warning(f"Конфигурация подсказки не найдена: {category}.{tooltip_id}")
            return
        
        # Сохраняем конфигурацию в виджете
        widget.tooltip_config = {
            'id': tooltip_id,
            'category': category,
            'config': tooltip_config,
            'custom_text': custom_text,
            'user_role': user_role
        }
        
        # Подключаем события
        widget.enterEvent = lambda event: self._on_widget_enter(widget, event)
        widget.leaveEvent = lambda event: self._on_widget_leave(widget, event)
        
        logger.debug(f"Зарегистрирована подсказка для виджета: {category}.{tooltip_id}")
    
    def _on_widget_enter(self, widget: QWidget, event):
        """Обработчик входа курсора в виджет."""
        self.current_widget = widget
        self.hide_timer.stop()
        
        # Запускаем таймер показа с задержкой
        self.show_timer.start(500)  # 500ms задержка
    
    def _on_widget_leave(self, widget: QWidget, event):
        """Обработчик выхода курсора из виджета."""
        self.show_timer.stop()
        
        if self.active_tooltip:
            # Запускаем таймер скрытия
            self.hide_timer.start(100)  # 100ms задержка
    
    def _show_tooltip(self):
        """Показывает подсказку для текущего виджета."""
        if not self.current_widget or not hasattr(self.current_widget, 'tooltip_config'):
            return
        
        config = self.current_widget.tooltip_config
        tooltip_text = self._generate_tooltip_text(config)
        icon = self._get_tooltip_icon(config)
        
        # Создаем подсказку
        self.active_tooltip = RichTooltip(tooltip_text, icon)
        
        # Позиционируем подсказку
        position = self._calculate_tooltip_position(self.current_widget)
        self.active_tooltip.move(position)
        
        # Показываем с анимацией
        self.active_tooltip.show_animated()
        
        logger.debug(f"Показана подсказка для: {config['category']}.{config['id']}")
    
    def _hide_tooltip(self):
        """Скрывает активную подсказку."""
        if self.active_tooltip:
            self.active_tooltip.hide_animated(lambda: self.active_tooltip.deleteLater())
            self.active_tooltip = None
    
    def _generate_tooltip_text(self, config: Dict[str, Any]) -> str:
        """
        Генерирует текст подсказки на основе конфигурации.
        
        Args:
            config: Конфигурация подсказки
            
        Returns:
            HTML текст подсказки
        """
        # Пользовательский текст имеет приоритет
        if config['custom_text']:
            return config['custom_text']
        
        tooltip_config = config['config']
        if not tooltip_config:
            return "Нет описания"
        
        html_parts = []
        
        # Основной текст
        main_text = tooltip_config.get('text', '')
        if main_text:
            html_parts.append(f"<b>{main_text}</b>")
        
        # Горячая клавиша
        hotkey = tooltip_config.get('hotkey')
        if hotkey:
            html_parts.append(f"<br><i>Горячая клавиша: <code>{hotkey}</code></i>")
        
        # Пример использования
        example = tooltip_config.get('example')
        if example:
            html_parts.append(f"<br><small>{example}</small>")
        
        # Предупреждение
        warning = tooltip_config.get('warning')
        if warning:
            html_parts.append(f"<br><font color='orange'>⚠️ {warning}</font>")
        
        # Функции (для таблиц и сложных элементов)
        features = tooltip_config.get('features')
        if features:
            features_text = "<br><small>Возможности:<ul>"
            for feature in features:
                features_text += f"<li>{feature}</li>"
            features_text += "</ul></small>"
            html_parts.append(features_text)
        
        # Информация о безопасности
        security = tooltip_config.get('security')
        if security:
            html_parts.append(f"<br><font color='lightblue'>🔒 {security}</font>")
        
        return "".join(html_parts)
    
    def _get_tooltip_icon(self, config: Dict[str, Any]) -> Optional[str]:
        """Получает иконку для подсказки."""
        tooltip_config = config['config']
        return tooltip_config.get('icon') if tooltip_config else None
    
    def _calculate_tooltip_position(self, widget: QWidget) -> QPoint:
        """
        Вычисляет оптимальную позицию для подсказки.
        
        Args:
            widget: Виджет-родитель
            
        Returns:
            Позиция для показа подсказки
        """
        if not widget:
            return QPoint(0, 0)
        
        # Получаем глобальную позицию виджета
        global_pos = widget.mapToGlobal(QPoint(0, 0))
        widget_size = widget.size()
        
        # Размеры экрана
        screen = QApplication.desktop().screenGeometry()
        
        # По умолчанию показываем снизу справа от виджета
        x = global_pos.x()
        y = global_pos.y() + widget_size.height() + 5
        
        # Проверяем границы экрана и корректируем позицию
        tooltip_width = 300  # Примерная ширина подсказки
        tooltip_height = 100  # Примерная высота подсказки
        
        # Корректировка по горизонтали
        if x + tooltip_width > screen.right():
            x = global_pos.x() + widget_size.width() - tooltip_width
        
        # Корректировка по вертикали
        if y + tooltip_height > screen.bottom():
            y = global_pos.y() - tooltip_height - 5
        
        return QPoint(max(0, x), max(0, y))
    
    def register_menu_items(self, menu_bar):
        """Регистрирует подсказки для элементов меню."""
        for action in menu_bar.actions():
            if action.menu():
                # Подменю
                menu_name = action.text().replace('&', '').lower()
                self.register_widget(action.menu(), menu_name, "menu")
                
                # Элементы подменю
                for sub_action in action.menu().actions():
                    if not sub_action.isSeparator():
                        action_name = sub_action.text().replace('&', '').lower()
                        # Для действий можем использовать их StatusTip как подсказку
                        if sub_action.statusTip():
                            self.register_widget(
                                sub_action,
                                action_name,
                                "menu",
                                sub_action.statusTip()
                            )
    
    def register_toolbar_buttons(self, toolbar):
        """Регистрирует подсказки для кнопок панели инструментов."""
        for action in toolbar.actions():
            if not action.isSeparator():
                # Получаем кнопку по действию
                button = toolbar.widgetForAction(action)
                if button:
                    action_text = action.text().lower()
                    
                    # Маппинг текста на ID подсказки
                    button_mapping = {
                        'добавить': 'add',
                        'редактировать': 'edit',
                        'удалить': 'delete',
                        'обновить': 'refresh',
                        'поиск': 'search',
                        'тема': 'theme_toggle'
                    }
                    
                    tooltip_id = button_mapping.get(action_text)
                    if tooltip_id:
                        self.register_widget(button, tooltip_id, "buttons")
    
    def save_tooltips_config(self):
        """Сохраняет конфигурацию подсказок."""
        config_dir = "resources/tooltips"
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, f"tooltips_{self.language}.json")
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.tooltips_config, f, ensure_ascii=False, indent=2)
            logger.info(f"Конфигурация подсказок сохранена: {config_path}")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации подсказок: {e}")
    
    def set_language(self, language: str):
        """Изменяет язык подсказок."""
        self.language = language
        self._load_tooltips_config()
        logger.info(f"Язык подсказок изменен на: {language}")


# Глобальный экземпляр менеджера подсказок
_tooltip_manager = None


def get_tooltip_manager(language: str = "ru") -> TooltipManager:
    """Возвращает глобальный экземпляр менеджера подсказок."""
    global _tooltip_manager
    if _tooltip_manager is None:
        _tooltip_manager = TooltipManager(language)
    return _tooltip_manager


def register_tooltips_for_window(window, user_role: str = None):
    """
    Удобная функция для регистрации подсказок для всего окна.
    
    Args:
        window: Главное окно приложения
        user_role: Роль пользователя для контекстных подсказок
    """
    tooltip_manager = get_tooltip_manager()
    
    # Регистрируем меню
    if hasattr(window, 'menuBar') and window.menuBar():
        tooltip_manager.register_menu_items(window.menuBar())
    
    # Регистрируем панель инструментов
    if hasattr(window, 'toolbar') and window.toolbar:
        tooltip_manager.register_toolbar_buttons(window.toolbar)
    
    # Регистрируем таблицы
    if hasattr(window, 'materials_table') and window.materials_table:
        tooltip_manager.register_widget(
            window.materials_table,
            'materials',
            'tables',
            user_role=user_role
        )
    
    logger.info(f"Подсказки зарегистрированы для окна с ролью пользователя: {user_role}") 