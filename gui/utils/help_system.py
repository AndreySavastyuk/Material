"""
Система контекстной справки для улучшения пользовательского опыта.

Особенности:
- Контекстная справка по F1
- Интерактивные руководства
- Поиск по справке
- Видео-туториалы
- Адаптивная справка для разных ролей
"""

import os
import json
from typing import Dict, Any, Optional, List, Union
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QLineEdit, QTreeWidget, QTreeWidgetItem, 
    QSplitter, QTabWidget, QWidget, QScrollArea, QFrame,
    QApplication, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QFont, QPixmap, QIcon, QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEngineView
from utils.logger import get_logger

logger = get_logger('gui.help_system')


class HelpContent:
    """
    Класс для содержимого справки.
    """
    
    def __init__(self, title: str, content: str, category: str = "general",
                 keywords: List[str] = None, images: List[str] = None,
                 video_url: str = None, user_roles: List[str] = None):
        self.title = title
        self.content = content
        self.category = category
        self.keywords = keywords or []
        self.images = images or []
        self.video_url = video_url
        self.user_roles = user_roles or ["all"]
    
    def matches_search(self, query: str) -> bool:
        """Проверяет соответствие поисковому запросу."""
        query_lower = query.lower()
        
        # Поиск в заголовке
        if query_lower in self.title.lower():
            return True
        
        # Поиск в контенте
        if query_lower in self.content.lower():
            return True
        
        # Поиск в ключевых словах
        for keyword in self.keywords:
            if query_lower in keyword.lower():
                return True
        
        return False
    
    def is_accessible_for_role(self, user_role: str) -> bool:
        """Проверяет доступность для роли пользователя."""
        return "all" in self.user_roles or user_role in self.user_roles


class InteractiveGuide(QDialog):
    """
    Интерактивное руководство с пошаговыми инструкциями.
    """
    
    def __init__(self, guide_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.guide_data = guide_data
        self.current_step = 0
        self.highlighted_widgets = []
        
        self.setWindowTitle(f"Руководство: {guide_data['title']}")
        self.setModal(False)
        self.resize(400, 300)
        
        self._setup_ui()
        self._show_current_step()
    
    def _setup_ui(self):
        """Настройка интерфейса руководства."""
        layout = QVBoxLayout()
        
        # Заголовок
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        # Содержимое шага
        self.content_label = QLabel()
        self.content_label.setWordWrap(True)
        self.content_label.setMinimumHeight(100)
        layout.addWidget(self.content_label)
        
        # Изображение (если есть)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumHeight(200)
        self.image_label.hide()
        layout.addWidget(self.image_label)
        
        # Прогресс
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("← Назад")
        self.prev_button.clicked.connect(self._prev_step)
        buttons_layout.addWidget(self.prev_button)
        
        self.step_label = QLabel()
        self.step_label.setAlignment(Qt.AlignCenter)
        buttons_layout.addWidget(self.step_label)
        
        self.next_button = QPushButton("Далее →")
        self.next_button.clicked.connect(self._next_step)
        buttons_layout.addWidget(self.next_button)
        
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def _show_current_step(self):
        """Показывает текущий шаг."""
        if not self.guide_data.get('steps'):
            return
        
        steps = self.guide_data['steps']
        if self.current_step >= len(steps):
            return
        
        step = steps[self.current_step]
        
        # Обновляем UI
        self.title_label.setText(step.get('title', ''))
        self.content_label.setText(step.get('content', ''))
        
        # Изображение
        image_path = step.get('image')
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
            self.image_label.show()
        else:
            self.image_label.hide()
        
        # Прогресс
        progress = int((self.current_step + 1) / len(steps) * 100)
        self.progress_bar.setValue(progress)
        
        # Кнопки
        self.prev_button.setEnabled(self.current_step > 0)
        self.next_button.setText("Завершить" if self.current_step == len(steps) - 1 else "Далее →")
        
        # Счетчик шагов
        self.step_label.setText(f"Шаг {self.current_step + 1} из {len(steps)}")
        
        # Подсветка элементов
        self._highlight_elements(step.get('highlight', []))
    
    def _next_step(self):
        """Переход к следующему шагу."""
        steps = self.guide_data.get('steps', [])
        
        if self.current_step < len(steps) - 1:
            self.current_step += 1
            self._show_current_step()
        else:
            self.close()
    
    def _prev_step(self):
        """Переход к предыдущему шагу."""
        if self.current_step > 0:
            self.current_step -= 1
            self._show_current_step()
    
    def _highlight_elements(self, element_names: List[str]):
        """Подсвечивает элементы интерфейса."""
        # Убираем предыдущую подсветку
        self._clear_highlights()
        
        # Найдем и подсветим элементы
        main_window = self.parent()
        if not main_window:
            return
        
        for element_name in element_names:
            widget = self._find_widget_by_name(main_window, element_name)
            if widget:
                self._add_highlight(widget)
    
    def _find_widget_by_name(self, parent, name: str):
        """Ищет виджет по имени."""
        if hasattr(parent, 'objectName') and parent.objectName() == name:
            return parent
        
        for child in parent.findChildren(QWidget):
            if child.objectName() == name:
                return child
        
        return None
    
    def _add_highlight(self, widget):
        """Добавляет подсветку к виджету."""
        # Простая подсветка через стиль
        original_style = widget.styleSheet()
        highlight_style = "border: 3px solid #FF6B35; border-radius: 5px;"
        
        widget.setStyleSheet(original_style + highlight_style)
        self.highlighted_widgets.append((widget, original_style))
    
    def _clear_highlights(self):
        """Убирает все подсветки."""
        for widget, original_style in self.highlighted_widgets:
            widget.setStyleSheet(original_style)
        self.highlighted_widgets.clear()
    
    def closeEvent(self, event):
        """Обработчик закрытия."""
        self._clear_highlights()
        super().closeEvent(event)


class HelpSearchWidget(QWidget):
    """
    Виджет поиска по справке.
    """
    
    search_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка интерфейса поиска."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText("Поиск по справке...")
        self.search_line.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_line)
        
        self.search_button = QPushButton("Найти")
        self.search_button.clicked.connect(self._do_search)
        layout.addWidget(self.search_button)
        
        self.setLayout(layout)
    
    def _on_search_changed(self, text: str):
        """Обработчик изменения текста поиска."""
        # Поиск с задержкой для избежания избыточных запросов
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()
        
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(lambda: self._do_search(text))
        self._search_timer.start(300)  # 300ms задержка
    
    def _do_search(self, text: str = None):
        """Выполняет поиск."""
        query = text or self.search_line.text()
        if query.strip():
            self.search_requested.emit(query.strip())


class HelpSystem(QDialog):
    """
    Главное окно системы справки.
    
    Особенности:
    - Иерархическая структура справки
    - Поиск по содержимому
    - Интерактивные руководства
    - Контекстная справка
    - Поддержка ролей пользователей
    """
    
    def __init__(self, user_role: str = "user", parent=None):
        super().__init__(parent)
        self.user_role = user_role
        self.help_contents: Dict[str, HelpContent] = {}
        self.current_context = "general"
        
        self.setWindowTitle("Справочная система")
        self.setModal(False)
        self.resize(900, 600)
        
        self._setup_ui()
        self._load_help_content()
        self._populate_tree()
        
        logger.info(f"HelpSystem инициализирована для роли: {user_role}")
    
    def _setup_ui(self):
        """Настройка интерфейса справки."""
        layout = QVBoxLayout()
        
        # Поиск
        self.search_widget = HelpSearchWidget()
        self.search_widget.search_requested.connect(self._search_help)
        layout.addWidget(self.search_widget)
        
        # Основная область
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - дерево разделов
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Заголовок дерева
        tree_label = QLabel("Разделы справки")
        tree_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        left_layout.addWidget(tree_label)
        
        # Дерево разделов
        self.help_tree = QTreeWidget()
        self.help_tree.setHeaderLabel("Содержание")
        self.help_tree.itemClicked.connect(self._on_tree_item_clicked)
        left_layout.addWidget(self.help_tree)
        
        # Кнопки быстрых действий
        quick_actions_label = QLabel("Быстрые действия")
        quick_actions_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        left_layout.addWidget(quick_actions_label)
        
        self.hotkeys_button = QPushButton("Горячие клавиши")
        self.hotkeys_button.clicked.connect(self.show_hotkeys_help)
        left_layout.addWidget(self.hotkeys_button)
        
        self.tour_button = QPushButton("Обзор интерфейса")
        self.tour_button.clicked.connect(self.start_interface_tour)
        left_layout.addWidget(self.tour_button)
        
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # Правая панель - содержимое
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Заголовок содержимого
        self.content_title = QLabel("Выберите раздел справки")
        self.content_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        right_layout.addWidget(self.content_title)
        
        # Вкладки содержимого
        self.content_tabs = QTabWidget()
        
        # Текстовое содержимое
        self.text_content = QTextEdit()
        self.text_content.setReadOnly(True)
        self.content_tabs.addTab(self.text_content, "Справка")
        
        # Веб-содержимое (для видео и интерактивного контента)
        try:
            self.web_content = QWebEngineView()
            self.content_tabs.addTab(self.web_content, "Видео")
        except ImportError:
            logger.warning("QWebEngineView недоступен, видео-контент отключен")
            self.web_content = None
        
        right_layout.addWidget(self.content_tabs)
        
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        # Пропорции панелей
        splitter.setSizes([250, 650])
        
        layout.addWidget(splitter)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.print_button = QPushButton("Печать")
        self.print_button.clicked.connect(self._print_help)
        buttons_layout.addWidget(self.print_button)
        
        buttons_layout.addStretch()
        
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def _load_help_content(self):
        """Загружает содержимое справки."""
        # Загружаем из JSON файла
        help_file = "resources/help/help_content.json"
        
        if os.path.exists(help_file):
            try:
                with open(help_file, 'r', encoding='utf-8') as f:
                    help_data = json.load(f)
                
                for content_id, data in help_data.items():
                    self.help_contents[content_id] = HelpContent(
                        title=data['title'],
                        content=data['content'],
                        category=data.get('category', 'general'),
                        keywords=data.get('keywords', []),
                        images=data.get('images', []),
                        video_url=data.get('video_url'),
                        user_roles=data.get('user_roles', ['all'])
                    )
                
                logger.debug(f"Загружено {len(self.help_contents)} разделов справки")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки справки: {e}")
                self._create_default_help()
        else:
            logger.warning(f"Файл справки не найден: {help_file}")
            self._create_default_help()
    
    def _create_default_help(self):
        """Создает базовое содержимое справки."""
        default_content = {
            "getting_started": HelpContent(
                title="Начало работы",
                content="""
                <h2>Добро пожаловать в систему контроля материалов!</h2>
                
                <p>Эта система предназначена для учета и контроля качества металлопроката.</p>
                
                <h3>Основные возможности:</h3>
                <ul>
                <li>Учет материалов и их характеристик</li>
                <li>Лабораторные исследования</li>
                <li>Контроль качества (ОТК)</li>
                <li>Генерация отчетов и сертификатов</li>
                <li>Управление пользователями и правами доступа</li>
                </ul>
                
                <h3>Первые шаги:</h3>
                <ol>
                <li>Войдите в систему под своими учетными данными</li>
                <li>Ознакомьтесь с интерфейсом</li>
                <li>Изучите доступные функции в зависимости от вашей роли</li>
                </ol>
                """,
                category="general",
                keywords=["начало", "старт", "введение", "обзор"],
                user_roles=["all"]
            ),
            
            "interface": HelpContent(
                title="Интерфейс программы",
                content="""
                <h2>Интерфейс системы</h2>
                
                <h3>Главное окно</h3>
                <p>Главное окно состоит из следующих элементов:</p>
                <ul>
                <li><b>Меню</b> - основные команды и настройки</li>
                <li><b>Панель инструментов</b> - быстрый доступ к часто используемым функциям</li>
                <li><b>Рабочая область</b> - таблицы данных и формы</li>
                <li><b>Статусная строка</b> - информация о состоянии системы</li>
                </ul>
                
                <h3>Горячие клавиши</h3>
                <p>Нажмите <b>Ctrl+?</b> для просмотра всех горячих клавиш.</p>
                
                <h3>Темы оформления</h3>
                <p>Вы можете переключаться между светлой и темной темами через меню "Вид" или нажав <b>Ctrl+T</b>.</p>
                """,
                category="interface",
                keywords=["интерфейс", "меню", "панель", "горячие клавиши", "темы"],
                user_roles=["all"]
            ),
            
            "materials": HelpContent(
                title="Работа с материалами",
                content="""
                <h2>Управление материалами</h2>
                
                <h3>Добавление материала</h3>
                <ol>
                <li>Нажмите кнопку "Добавить" или <b>Ctrl+N</b></li>
                <li>Заполните обязательные поля</li>
                <li>Укажите поставщика и характеристики</li>
                <li>Сохраните изменения</li>
                </ol>
                
                <h3>Редактирование материала</h3>
                <ol>
                <li>Выберите материал в таблице</li>
                <li>Нажмите кнопку "Редактировать" или <b>Ctrl+E</b></li>
                <li>Внесите необходимые изменения</li>
                <li>Сохраните изменения</li>
                </ol>
                
                <h3>Поиск материалов</h3>
                <p>Используйте поле поиска (<b>Ctrl+F</b>) для быстрого поиска по названию, артикулу или другим характеристикам.</p>
                """,
                category="materials",
                keywords=["материалы", "добавление", "редактирование", "поиск"],
                user_roles=["admin", "manager", "lab", "otk"]
            ),
            
            "lab": HelpContent(
                title="Лабораторные исследования",
                content="""
                <h2>Лабораторный модуль</h2>
                
                <h3>Создание заявки на исследование</h3>
                <ol>
                <li>Выберите материал для исследования</li>
                <li>Укажите тип исследования</li>
                <li>Заполните параметры испытаний</li>
                <li>Отправьте заявку на утверждение</li>
                </ol>
                
                <h3>Ввод результатов</h3>
                <ol>
                <li>Откройте утвержденную заявку</li>
                <li>Введите результаты измерений</li>
                <li>Добавьте фотографии образцов (при необходимости)</li>
                <li>Сформируйте протокол испытаний</li>
                </ol>
                
                <h3>Генерация сертификатов</h3>
                <p>После ввода всех результатов система автоматически сформирует сертификат качества.</p>
                """,
                category="lab",
                keywords=["лаборатория", "исследования", "протокол", "сертификат"],
                user_roles=["admin", "lab"]
            ),
            
            "otk": HelpContent(
                title="Отдел технического контроля",
                content="""
                <h2>Модуль ОТК</h2>
                
                <h3>Визуальный контроль</h3>
                <ol>
                <li>Выберите материал для контроля</li>
                <li>Зафиксируйте обнаруженные дефекты</li>
                <li>Сделайте фотографии дефектов</li>
                <li>Примите решение о соответствии</li>
                </ol>
                
                <h3>Контроль размеров</h3>
                <ol>
                <li>Измерьте фактические размеры</li>
                <li>Сравните с нормативными значениями</li>
                <li>Зафиксируйте отклонения</li>
                <li>Оформите заключение</li>
                </ol>
                """,
                category="otk",
                keywords=["отк", "контроль", "дефекты", "размеры"],
                user_roles=["admin", "otk"]
            )
        }
        
        self.help_contents = default_content
    
    def _populate_tree(self):
        """Заполняет дерево разделов справки."""
        self.help_tree.clear()
        
        # Группируем по категориям
        categories = {}
        for content_id, content in self.help_contents.items():
            if not content.is_accessible_for_role(self.user_role):
                continue
            
            category = content.category
            if category not in categories:
                categories[category] = []
            categories[category].append((content_id, content))
        
        # Создаем элементы дерева
        category_names = {
            "general": "Общие",
            "interface": "Интерфейс",
            "materials": "Материалы",
            "lab": "Лаборатория",
            "otk": "ОТК",
            "admin": "Администрирование"
        }
        
        for category, contents in categories.items():
            category_item = QTreeWidgetItem(self.help_tree)
            category_item.setText(0, category_names.get(category, category.title()))
            category_item.setData(0, Qt.UserRole, f"category:{category}")
            
            for content_id, content in contents:
                content_item = QTreeWidgetItem(category_item)
                content_item.setText(0, content.title)
                content_item.setData(0, Qt.UserRole, f"content:{content_id}")
        
        # Разворачиваем все категории
        self.help_tree.expandAll()
    
    def _on_tree_item_clicked(self, item, column):
        """Обработчик клика по элементу дерева."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        if data.startswith("content:"):
            content_id = data[8:]  # Убираем "content:"
            self._show_content(content_id)
    
    def _show_content(self, content_id: str):
        """Показывает содержимое справки."""
        if content_id not in self.help_contents:
            return
        
        content = self.help_contents[content_id]
        
        # Обновляем заголовок
        self.content_title.setText(content.title)
        
        # Показываем текстовое содержимое
        self.text_content.setHtml(content.content)
        
        # Показываем видео (если есть)
        if self.web_content and content.video_url:
            self.web_content.setUrl(QUrl(content.video_url))
            self.content_tabs.setCurrentWidget(self.web_content)
        else:
            self.content_tabs.setCurrentWidget(self.text_content)
    
    def _search_help(self, query: str):
        """Выполняет поиск по справке."""
        results = []
        
        for content_id, content in self.help_contents.items():
            if not content.is_accessible_for_role(self.user_role):
                continue
            
            if content.matches_search(query):
                results.append((content_id, content))
        
        # Показываем результаты поиска
        self._show_search_results(query, results)
    
    def _show_search_results(self, query: str, results: List):
        """Показывает результаты поиска."""
        if not results:
            html = f"<h2>Результаты поиска для '{query}'</h2><p>Ничего не найдено.</p>"
        else:
            html = f"<h2>Результаты поиска для '{query}'</h2>"
            html += f"<p>Найдено результатов: {len(results)}</p>"
            
            for content_id, content in results:
                html += f"""
                <div style="border: 1px solid #ccc; margin: 10px 0; padding: 10px; border-radius: 5px;">
                    <h3><a href="#" onclick="showContent('{content_id}')">{content.title}</a></h3>
                    <p><strong>Категория:</strong> {content.category}</p>
                    <p>{content.content[:200]}...</p>
                </div>
                """
        
        self.content_title.setText(f"Поиск: {query}")
        self.text_content.setHtml(html)
    
    def show_context_help(self, context: str):
        """
        Показывает контекстную справку для определенного раздела.
        
        Args:
            context: Контекст (например, "materials", "lab")
        """
        self.current_context = context
        
        # Ищем подходящий контент
        for content_id, content in self.help_contents.items():
            if content.category == context:
                self._show_content(content_id)
                break
        
        self.show()
        self.raise_()
        self.activateWindow()
    
    def show_hotkeys_help(self):
        """Показывает справку по горячим клавишам."""
        try:
            from .hotkey_manager import get_hotkey_manager
            hotkey_manager = get_hotkey_manager()
            
            html = "<h2>Горячие клавиши</h2>"
            
            categories = hotkey_manager.get_categories()
            for category in categories:
                html += f"<h3>{category.title()}</h3><ul>"
                
                actions = hotkey_manager.get_actions_by_category(category)
                for action in sorted(actions, key=lambda a: a.description):
                    if action.enabled:
                        html += f"<li><b>{action.key_sequence}</b> - {action.description}</li>"
                
                html += "</ul>"
            
            self.content_title.setText("Горячие клавиши")
            self.text_content.setHtml(html)
            
        except ImportError:
            self.content_title.setText("Горячие клавиши")
            self.text_content.setHtml("<p>Система горячих клавиш недоступна.</p>")
    
    def start_interface_tour(self):
        """Запускает обзор интерфейса."""
        tour_data = {
            'title': 'Обзор интерфейса',
            'steps': [
                {
                    'title': 'Главное меню',
                    'content': 'В главном меню находятся все основные команды программы',
                    'highlight': ['menubar']
                },
                {
                    'title': 'Панель инструментов',
                    'content': 'Панель инструментов обеспечивает быстрый доступ к часто используемым функциям',
                    'highlight': ['toolbar']
                },
                {
                    'title': 'Рабочая область',
                    'content': 'В рабочей области отображаются таблицы данных и формы редактирования',
                    'highlight': ['central_widget']
                },
                {
                    'title': 'Статусная строка',
                    'content': 'Статусная строка показывает информацию о состоянии системы',
                    'highlight': ['statusbar']
                }
            ]
        }
        
        guide = InteractiveGuide(tour_data, self.parent())
        guide.show()
    
    def _print_help(self):
        """Печатает текущий раздел справки."""
        try:
            from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
            
            printer = QPrinter()
            dialog = QPrintDialog(printer, self)
            
            if dialog.exec_() == QPrintDialog.Accepted:
                self.text_content.print_(printer)
                
        except ImportError:
            QMessageBox.information(
                self,
                "Печать",
                "Функция печати недоступна"
            )


# Глобальный экземпляр системы справки
_help_system = None


def get_help_system(user_role: str = "user", parent=None) -> HelpSystem:
    """Возвращает глобальный экземпляр системы справки."""
    global _help_system
    if _help_system is None:
        _help_system = HelpSystem(user_role, parent)
    return _help_system


def show_context_help(context: str, user_role: str = "user", parent=None):
    """
    Удобная функция для показа контекстной справки.
    
    Args:
        context: Контекст справки
        user_role: Роль пользователя
        parent: Родительское окно
    """
    help_system = get_help_system(user_role, parent)
    help_system.show_context_help(context)


def create_help_content_files():
    """Создает файлы содержимого справки."""
    help_dir = "resources/help"
    os.makedirs(help_dir, exist_ok=True)
    
    # Создаем базовый файл содержимого
    # (содержимое уже определено в _create_default_help)
    
    logger.info("Файлы справки созданы") 