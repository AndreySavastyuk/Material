"""
Система автозаполнения полей ввода для улучшения пользовательского опыта.

Особенности:
- Интеллектуальные предложения на основе истории
- Нечеткий поиск и исправление опечаток
- Кэширование для быстродействия
- Настраиваемые источники данных
- Контекстные предложения
"""

import os
import json
import sqlite3
from typing import List, Dict, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QLineEdit, QCompleter, QListWidget, QListWidgetItem, 
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QScrollArea, QApplication
)
from PyQt5.QtCore import (
    Qt, QStringListModel, QAbstractListModel, QModelIndex, 
    QVariant, QTimer, pyqtSignal, QThread, QObject
)
from PyQt5.QtGui import QFont, QPalette
from difflib import SequenceMatcher
from utils.logger import get_logger

logger = get_logger('gui.autocomplete_manager')


class AutoCompleteItem:
    """
    Элемент автозаполнения.
    """
    
    def __init__(self, text: str, category: str = "general", 
                 weight: float = 1.0, metadata: Dict = None):
        self.text = text
        self.category = category
        self.weight = weight  # Вес для сортировки
        self.metadata = metadata or {}
        self.usage_count = 0
        self.last_used = None
        self.created_at = datetime.now()
    
    def use(self):
        """Отмечает использование элемента."""
        self.usage_count += 1
        self.last_used = datetime.now()
        self.weight += 0.1  # Увеличиваем вес при использовании
    
    def calculate_relevance(self, query: str) -> float:
        """
        Вычисляет релевантность элемента для запроса.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Оценка релевантности от 0 до 1
        """
        if not query:
            return 0.0
        
        text_lower = self.text.lower()
        query_lower = query.lower()
        
        # Точное совпадение в начале
        if text_lower.startswith(query_lower):
            return 1.0
        
        # Совпадение в любом месте
        if query_lower in text_lower:
            return 0.8
        
        # Нечеткое совпадение
        similarity = SequenceMatcher(None, query_lower, text_lower).ratio()
        if similarity > 0.6:
            return similarity * 0.6
        
        # Проверяем совпадение по словам
        query_words = query_lower.split()
        text_words = text_lower.split()
        
        word_matches = 0
        for query_word in query_words:
            for text_word in text_words:
                if query_word in text_word or text_word in query_word:
                    word_matches += 1
                    break
        
        if word_matches > 0:
            return (word_matches / len(query_words)) * 0.5
        
        return 0.0
    
    def __str__(self):
        return self.text
    
    def __repr__(self):
        return f"AutoCompleteItem('{self.text}', weight={self.weight})"


class SmartCompleterModel(QAbstractListModel):
    """
    Умная модель для автозаполнения с поддержкой весов и категорий.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[AutoCompleteItem] = []
        self.filtered_items: List[AutoCompleteItem] = []
        self.current_query = ""
    
    def rowCount(self, parent=QModelIndex()) -> int:
        """Возвращает количество строк."""
        return len(self.filtered_items)
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> QVariant:
        """Возвращает данные для индекса."""
        if not index.isValid() or index.row() >= len(self.filtered_items):
            return QVariant()
        
        item = self.filtered_items[index.row()]
        
        if role == Qt.DisplayRole:
            return item.text
        elif role == Qt.UserRole:
            return item
        elif role == Qt.ToolTipRole:
            tooltip = f"Категория: {item.category}\n"
            tooltip += f"Использований: {item.usage_count}\n"
            if item.last_used:
                tooltip += f"Последнее использование: {item.last_used.strftime('%Y-%m-%d %H:%M')}"
            return tooltip
        
        return QVariant()
    
    def add_item(self, item: AutoCompleteItem):
        """Добавляет элемент в модель."""
        if item not in self.items:
            self.beginInsertRows(QModelIndex(), len(self.items), len(self.items))
            self.items.append(item)
            self.endInsertRows()
    
    def remove_item(self, item: AutoCompleteItem):
        """Удаляет элемент из модели."""
        if item in self.items:
            index = self.items.index(item)
            self.beginRemoveRows(QModelIndex(), index, index)
            self.items.remove(item)
            self.endRemoveRows()
    
    def set_filter(self, query: str):
        """Устанавливает фильтр для поиска."""
        self.current_query = query
        self.beginResetModel()
        
        if not query:
            self.filtered_items = self.items[:]
        else:
            # Вычисляем релевантность и фильтруем
            scored_items = []
            for item in self.items:
                relevance = item.calculate_relevance(query)
                if relevance > 0:
                    scored_items.append((item, relevance))
            
            # Сортируем по релевантности и весу
            scored_items.sort(key=lambda x: (x[1], x[0].weight), reverse=True)
            self.filtered_items = [item for item, _ in scored_items[:20]]  # Ограничиваем до 20
        
        self.endResetModel()
    
    def get_item_at(self, index: int) -> Optional[AutoCompleteItem]:
        """Возвращает элемент по индексу."""
        if 0 <= index < len(self.filtered_items):
            return self.filtered_items[index]
        return None


class EnhancedCompleter(QCompleter):
    """
    Улучшенный completer с дополнительными возможностями.
    """
    
    item_selected = pyqtSignal(AutoCompleteItem)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.smart_model = SmartCompleterModel()
        self.setModel(self.smart_model)
        
        # Настройки
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setMaxVisibleItems(10)
        
        # Подключаем сигналы
        self.activated[QModelIndex].connect(self._on_completion_selected)
    
    def _on_completion_selected(self, index: QModelIndex):
        """Обработчик выбора предложения."""
        item = self.smart_model.get_item_at(index.row())
        if item:
            item.use()  # Отмечаем использование
            self.item_selected.emit(item)
    
    def set_filter(self, text: str):
        """Устанавливает фильтр поиска."""
        self.smart_model.set_filter(text)
    
    def add_item(self, item: AutoCompleteItem):
        """Добавляет элемент автозаполнения."""
        self.smart_model.add_item(item)


class AutoCompleteLineEdit(QLineEdit):
    """
    Поле ввода с улучшенным автозаполнением.
    """
    
    def __init__(self, category: str = "general", parent=None):
        super().__init__(parent)
        self.category = category
        self.autocomplete_manager = None
        self.enhanced_completer = None
        self.suggestions_widget = None
        
        # Таймер для задержки поиска
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        
        self.textChanged.connect(self._on_text_changed)
    
    def set_autocomplete_manager(self, manager):
        """Устанавливает менеджер автозаполнения."""
        self.autocomplete_manager = manager
        
        # Создаем enhanced completer
        self.enhanced_completer = EnhancedCompleter(self)
        self.enhanced_completer.item_selected.connect(self._on_item_selected)
        
        # Загружаем предложения для категории
        self._load_suggestions()
        
        # Устанавливаем completer
        self.setCompleter(self.enhanced_completer)
    
    def _load_suggestions(self):
        """Загружает предложения для текущей категории."""
        if not self.autocomplete_manager:
            return
        
        suggestions = self.autocomplete_manager.get_suggestions(self.category)
        for suggestion in suggestions:
            self.enhanced_completer.add_item(suggestion)
    
    def _on_text_changed(self, text: str):
        """Обработчик изменения текста."""
        # Запускаем поиск с задержкой
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms задержка
    
    def _perform_search(self):
        """Выполняет поиск предложений."""
        text = self.text()
        
        if self.enhanced_completer:
            self.enhanced_completer.set_filter(text)
        
        # Запрашиваем дополнительные предложения у менеджера
        if self.autocomplete_manager and len(text) >= 2:
            self.autocomplete_manager.request_suggestions(text, self.category)
    
    def _on_item_selected(self, item: AutoCompleteItem):
        """Обработчик выбора элемента автозаполнения."""
        # Сохраняем использование в менеджере
        if self.autocomplete_manager:
            self.autocomplete_manager.record_usage(item, self.category)


class SuggestionProvider:
    """
    Базовый класс для поставщиков предложений автозаполнения.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    def get_suggestions(self, query: str, category: str, limit: int = 20) -> List[AutoCompleteItem]:
        """
        Возвращает предложения для запроса.
        
        Args:
            query: Поисковый запрос
            category: Категория поиска
            limit: Максимальное количество предложений
            
        Returns:
            Список предложений
        """
        raise NotImplementedError()


class DatabaseSuggestionProvider(SuggestionProvider):
    """
    Поставщик предложений из базы данных.
    """
    
    def __init__(self, db_path: str):
        super().__init__("database")
        self.db_path = db_path
    
    def get_suggestions(self, query: str, category: str, limit: int = 20) -> List[AutoCompleteItem]:
        """Получает предложения из БД."""
        suggestions = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Маппинг категорий на таблицы/поля
                category_mapping = {
                    'material_name': ('materials', 'name'),
                    'supplier': ('suppliers', 'name'),
                    'grade': ('grades', 'name'),
                    'size': ('sizes', 'value'),
                    'user_name': ('users', 'username')
                }
                
                if category in category_mapping:
                    table, field = category_mapping[category]
                    
                    # Поиск с LIKE
                    cursor.execute(
                        f"SELECT DISTINCT {field} FROM {table} WHERE {field} LIKE ? ORDER BY {field} LIMIT ?",
                        (f"%{query}%", limit)
                    )
                    
                    for row in cursor.fetchall():
                        item = AutoCompleteItem(
                            text=row[0],
                            category=category,
                            weight=1.0,
                            metadata={'source': 'database', 'table': table}
                        )
                        suggestions.append(item)
                        
        except Exception as e:
            logger.error(f"Ошибка получения предложений из БД: {e}")
        
        return suggestions


class HistorySuggestionProvider(SuggestionProvider):
    """
    Поставщик предложений на основе истории использования.
    """
    
    def __init__(self, history_file: str):
        super().__init__("history")
        self.history_file = history_file
        self.history_data = self._load_history()
    
    def _load_history(self) -> Dict[str, List[Dict]]:
        """Загружает историю из файла."""
        if not os.path.exists(self.history_file):
            return {}
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки истории автозаполнения: {e}")
            return {}
    
    def save_history(self):
        """Сохраняет историю в файл."""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения истории автозаполнения: {e}")
    
    def get_suggestions(self, query: str, category: str, limit: int = 20) -> List[AutoCompleteItem]:
        """Получает предложения из истории."""
        suggestions = []
        
        category_history = self.history_data.get(category, [])
        
        for entry in category_history:
            item = AutoCompleteItem(
                text=entry['text'],
                category=category,
                weight=entry.get('weight', 1.0),
                metadata={'source': 'history'}
            )
            item.usage_count = entry.get('usage_count', 0)
            
            if entry.get('last_used'):
                item.last_used = datetime.fromisoformat(entry['last_used'])
            
            # Проверяем релевантность
            if item.calculate_relevance(query) > 0:
                suggestions.append(item)
        
        # Сортируем по релевантности и весу
        suggestions.sort(key=lambda x: (x.calculate_relevance(query), x.weight), reverse=True)
        
        return suggestions[:limit]
    
    def add_to_history(self, item: AutoCompleteItem, category: str):
        """Добавляет элемент в историю."""
        if category not in self.history_data:
            self.history_data[category] = []
        
        # Ищем существующий элемент
        existing = None
        for entry in self.history_data[category]:
            if entry['text'] == item.text:
                existing = entry
                break
        
        if existing:
            # Обновляем существующий
            existing['usage_count'] = item.usage_count
            existing['weight'] = item.weight
            existing['last_used'] = item.last_used.isoformat() if item.last_used else None
        else:
            # Добавляем новый
            entry = {
                'text': item.text,
                'weight': item.weight,
                'usage_count': item.usage_count,
                'last_used': item.last_used.isoformat() if item.last_used else None
            }
            self.history_data[category].append(entry)
        
        # Ограничиваем размер истории
        if len(self.history_data[category]) > 1000:
            # Удаляем самые старые и редко используемые
            self.history_data[category].sort(
                key=lambda x: (x.get('usage_count', 0), x.get('last_used', '')), 
                reverse=True
            )
            self.history_data[category] = self.history_data[category][:1000]


class AutoCompleteManager(QObject):
    """
    Главный менеджер системы автозаполнения.
    
    Особенности:
    - Множественные источники данных
    - Кэширование предложений
    - Обучение на основе использования
    - Контекстные предложения
    - Оптимизация производительности
    """
    
    suggestions_ready = pyqtSignal(str, list)  # category, suggestions
    
    def __init__(self):
        super().__init__()
        self.providers: List[SuggestionProvider] = []
        self.cache: Dict[str, List[AutoCompleteItem]] = {}
        self.cache_timeout = 300  # 5 минут
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # История
        self.history_provider = HistorySuggestionProvider("resources/autocomplete_history.json")
        self.providers.append(self.history_provider)
        
        # БД
        if os.path.exists("materials.db"):
            self.db_provider = DatabaseSuggestionProvider("materials.db")
            self.providers.append(self.db_provider)
        
        # Таймер для сохранения истории
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_history)
        
        logger.info(f"AutoCompleteManager инициализирован с {len(self.providers)} поставщиками")
    
    def get_suggestions(self, category: str, limit: int = 20) -> List[AutoCompleteItem]:
        """
        Получает предложения для категории.
        
        Args:
            category: Категория предложений
            limit: Максимальное количество
            
        Returns:
            Список предложений
        """
        cache_key = f"{category}:all"
        
        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key][:limit]
        
        # Собираем предложения от всех поставщиков
        all_suggestions = []
        
        for provider in self.providers:
            try:
                suggestions = provider.get_suggestions("", category, limit)
                all_suggestions.extend(suggestions)
            except Exception as e:
                logger.error(f"Ошибка получения предложений от {provider.name}: {e}")
        
        # Удаляем дубликаты и сортируем
        unique_suggestions = []
        seen_texts = set()
        
        for suggestion in all_suggestions:
            if suggestion.text not in seen_texts:
                unique_suggestions.append(suggestion)
                seen_texts.add(suggestion.text)
        
        # Сортируем по весу
        unique_suggestions.sort(key=lambda x: x.weight, reverse=True)
        
        # Кэшируем результат
        self.cache[cache_key] = unique_suggestions
        self.cache_timestamps[cache_key] = datetime.now()
        
        return unique_suggestions[:limit]
    
    def request_suggestions(self, query: str, category: str, limit: int = 20):
        """
        Асинхронно запрашивает предложения для запроса.
        
        Args:
            query: Поисковый запрос
            category: Категория поиска
            limit: Максимальное количество
        """
        cache_key = f"{category}:{query}"
        
        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            self.suggestions_ready.emit(category, self.cache[cache_key][:limit])
            return
        
        # Запускаем поиск в отдельном потоке
        from PyQt5.QtCore import QThreadPool, QRunnable
        
        class SuggestionWorker(QRunnable):
            def __init__(self, manager, query, category, limit):
                super().__init__()
                self.manager = manager
                self.query = query
                self.category = category
                self.limit = limit
            
            def run(self):
                suggestions = []
                
                for provider in self.manager.providers:
                    try:
                        provider_suggestions = provider.get_suggestions(self.query, self.category, self.limit)
                        suggestions.extend(provider_suggestions)
                    except Exception as e:
                        logger.error(f"Ошибка получения предложений от {provider.name}: {e}")
                
                # Удаляем дубликаты и сортируем
                unique_suggestions = []
                seen_texts = set()
                
                for suggestion in suggestions:
                    if suggestion.text not in seen_texts:
                        unique_suggestions.append(suggestion)
                        seen_texts.add(suggestion.text)
                
                # Сортируем по релевантности
                unique_suggestions.sort(
                    key=lambda x: (x.calculate_relevance(self.query), x.weight), 
                    reverse=True
                )
                
                result = unique_suggestions[:self.limit]
                
                # Кэшируем и отправляем результат
                self.manager.cache[cache_key] = result
                self.manager.cache_timestamps[cache_key] = datetime.now()
                self.manager.suggestions_ready.emit(self.category, result)
        
        worker = SuggestionWorker(self, query, category, limit)
        QThreadPool.globalInstance().start(worker)
    
    def record_usage(self, item: AutoCompleteItem, category: str):
        """
        Записывает использование элемента автозаполнения.
        
        Args:
            item: Использованный элемент
            category: Категория элемента
        """
        # Добавляем в историю
        self.history_provider.add_to_history(item, category)
        
        # Очищаем кэш для этой категории
        self._clear_category_cache(category)
        
        # Запускаем сохранение с задержкой
        self.save_timer.start(5000)  # 5 секунд
        
        logger.debug(f"Записано использование: {item.text} в категории {category}")
    
    def add_suggestion(self, text: str, category: str, weight: float = 1.0, metadata: Dict = None):
        """
        Добавляет новое предложение.
        
        Args:
            text: Текст предложения
            category: Категория
            weight: Вес предложения
            metadata: Дополнительные данные
        """
        item = AutoCompleteItem(text, category, weight, metadata)
        self.history_provider.add_to_history(item, category)
        
        # Очищаем кэш
        self._clear_category_cache(category)
        
        logger.debug(f"Добавлено предложение: {text} в категории {category}")
    
    def create_line_edit(self, category: str, parent=None) -> AutoCompleteLineEdit:
        """
        Создает поле ввода с автозаполнением.
        
        Args:
            category: Категория автозаполнения
            parent: Родительский виджет
            
        Returns:
            Поле ввода с настроенным автозаполнением
        """
        line_edit = AutoCompleteLineEdit(category, parent)
        line_edit.set_autocomplete_manager(self)
        return line_edit
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Проверяет актуальность кэша."""
        if cache_key not in self.cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age = (datetime.now() - self.cache_timestamps[cache_key]).total_seconds()
        return age < self.cache_timeout
    
    def _clear_category_cache(self, category: str):
        """Очищает кэш для категории."""
        keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"{category}:")]
        
        for key in keys_to_remove:
            del self.cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    def _save_history(self):
        """Сохраняет историю автозаполнения."""
        try:
            self.history_provider.save_history()
            logger.debug("История автозаполнения сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения истории автозаполнения: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику использования."""
        stats = {
            'providers_count': len(self.providers),
            'cache_entries': len(self.cache),
            'categories': set()
        }
        
        # Собираем категории из истории
        for category in self.history_provider.history_data.keys():
            stats['categories'].add(category)
        
        stats['categories'] = list(stats['categories'])
        
        return stats


# Глобальный экземпляр менеджера автозаполнения
_autocomplete_manager = None


def get_autocomplete_manager() -> AutoCompleteManager:
    """Возвращает глобальный экземпляр менеджера автозаполнения."""
    global _autocomplete_manager
    if _autocomplete_manager is None:
        _autocomplete_manager = AutoCompleteManager()
    return _autocomplete_manager


def create_autocomplete_line_edit(category: str, parent=None) -> AutoCompleteLineEdit:
    """
    Удобная функция для создания поля с автозаполнением.
    
    Args:
        category: Категория автозаполнения
        parent: Родительский виджет
        
    Returns:
        Настроенное поле ввода
    """
    manager = get_autocomplete_manager()
    return manager.create_line_edit(category, parent)


def setup_autocomplete_for_widget(widget: QLineEdit, category: str):
    """
    Настраивает автозаполнение для существующего виджета.
    
    Args:
        widget: Поле ввода
        category: Категория автозаполнения
    """
    if not isinstance(widget, AutoCompleteLineEdit):
        logger.warning("Виджет должен быть типа AutoCompleteLineEdit для полной поддержки автозаполнения")
        return
    
    manager = get_autocomplete_manager()
    widget.set_autocomplete_manager(manager) 