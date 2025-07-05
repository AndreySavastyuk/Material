"""
Утилиты для работы с конфигурацией приложения.
"""

import os
from typing import Dict, Any, Optional
from configparser import ConfigParser, NoSectionError, NoOptionError

DEFAULT_CONFIG = {
    'DATABASE': {
        'path': 'materials.db',
        'backup_path': 'backups/',
        'backup_interval': '24'  # часов
    },
    'DOCUMENTS': {
        'root_path': 'docs/',
        'max_file_size': '10485760',  # 10MB в байтах
        'allowed_extensions': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
    },
    'LOGGING': {
        'level': 'INFO',
        'file': 'app.log',
        'max_bytes': '10485760',  # 10MB
        'backup_count': '5'
    },
    'TELEGRAM': {
        'token': '',
        'chat_id': '',
        'enabled': 'false'
    }
}


class ConfigManager:
    """Менеджер конфигурации приложения."""
    
    def __init__(self, config_file: str = 'config.ini'):
        """
        Инициализация менеджера конфигурации.
        
        Args:
            config_file: Путь к файлу конфигурации
        """
        self.config_file = config_file
        self._config = ConfigParser()
        self._load_config()
    
    def _load_config(self) -> None:
        """Загрузка конфигурации из файла."""
        # Создаем конфигурацию по умолчанию
        for section, options in DEFAULT_CONFIG.items():
            if not self._config.has_section(section):
                self._config.add_section(section)
            for key, value in options.items():
                self._config.set(section, key, value)
        
        # Если файл существует, загружаем его
        if os.path.exists(self.config_file):
            self._config.read(self.config_file, encoding='utf-8')
        else:
            # Создаем файл с настройками по умолчанию
            self.save_config()
    
    def save_config(self) -> None:
        """Сохранение конфигурации в файл."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self._config.write(f)
    
    def get(self, section: str, key: str, default: Optional[str] = None) -> str:
        """
        Получение значения из конфигурации.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Значение конфигурации
        """
        try:
            return self._config.get(section, key)
        except (KeyError, NoSectionError, NoOptionError):
            return default or ''
    
    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """
        Получение целочисленного значения.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Целочисленное значение
        """
        try:
            return self._config.getint(section, key)
        except (ValueError, KeyError):
            return default
    
    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """
        Получение булева значения.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Булево значение
        """
        try:
            return self._config.getboolean(section, key)
        except (ValueError, KeyError):
            return default
    
    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """
        Получение дробного значения.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Дробное значение
        """
        try:
            return self._config.getfloat(section, key)
        except (ValueError, KeyError):
            return default
    
    def set(self, section: str, key: str, value: str) -> None:
        """
        Установка значения в конфигурации.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            value: Значение
        """
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, str(value))
    
    def get_section(self, section: str) -> Dict[str, str]:
        """
        Получение всех значений секции.
        
        Args:
            section: Секция конфигурации
            
        Returns:
            Словарь с парами ключ-значение
        """
        try:
            return dict(self._config.items(section))
        except:
            return {}
    
    def has_section(self, section: str) -> bool:
        """
        Проверка существования секции.
        
        Args:
            section: Секция конфигурации
            
        Returns:
            True если секция существует
        """
        return self._config.has_section(section)
    
    def has_option(self, section: str, key: str) -> bool:
        """
        Проверка существования опции.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            
        Returns:
            True если опция существует
        """
        return self._config.has_option(section, key)
    
    def remove_option(self, section: str, key: str) -> bool:
        """
        Удаление опции из секции.
        
        Args:
            section: Секция конфигурации
            key: Ключ
            
        Returns:
            True если опция была удалена
        """
        return self._config.remove_option(section, key)
    
    def remove_section(self, section: str) -> bool:
        """
        Удаление секции.
        
        Args:
            section: Секция конфигурации
            
        Returns:
            True если секция была удалена
        """
        return self._config.remove_section(section)


# Глобальный экземпляр менеджера конфигурации
config_manager = ConfigManager() 