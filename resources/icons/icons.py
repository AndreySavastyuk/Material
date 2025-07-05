"""
Генератор SVG иконок для системы контроля материалов.
Создает высококачественные векторные иконки для интерфейса.
"""

import os
from typing import Dict, Tuple


class IconGenerator:
    """Генератор SVG иконок с поддержкой тем."""
    
    def __init__(self, icons_dir: str = "resources/icons"):
        """
        Инициализация генератора.
        
        Args:
            icons_dir: Директория для сохранения иконок
        """
        self.icons_dir = icons_dir
        self.ensure_icons_dir()
    
    def ensure_icons_dir(self):
        """Создает директорию для иконок если она не существует."""
        os.makedirs(self.icons_dir, exist_ok=True)
    
    def get_theme_colors(self, theme: str = "light") -> Dict[str, str]:
        """
        Возвращает цвета для темы.
        
        Args:
            theme: Тип темы (light/dark)
            
        Returns:
            Словарь цветов
        """
        if theme == "dark":
            return {
                'primary': '#ffffff',
                'secondary': '#cccccc',
                'accent': '#0e7afe',
                'background': '#2b2b2b',
                'success': '#28a745',
                'warning': '#ffc107',
                'danger': '#dc3545',
                'info': '#17a2b8'
            }
        else:  # light
            return {
                'primary': '#2b2b2b',
                'secondary': '#666666',
                'accent': '#0078d4',
                'background': '#ffffff',
                'success': '#28a745',
                'warning': '#ffc107',
                'danger': '#dc3545',
                'info': '#17a2b8'
            }
    
    def create_app_logo(self, theme: str = "light") -> str:
        """Создает логотип приложения."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
            <!-- Основа логотипа - стилизованные металлические листы -->
            <defs>
                <linearGradient id="metalGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="{colors['accent']}" stop-opacity="1"/>
                    <stop offset="50%" stop-color="#106ebe" stop-opacity="1"/>
                    <stop offset="100%" stop-color="{colors['accent']}" stop-opacity="1"/>
                </linearGradient>
                <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="2" dy="2" stdDeviation="2" flood-color="{colors['secondary']}" flood-opacity="0.3"/>
                </filter>
            </defs>
            
            <!-- Задний металлический лист -->
            <rect x="18" y="20" width="28" height="18" rx="2" ry="2" 
                  fill="url(#metalGradient)" opacity="0.8" filter="url(#shadow)"/>
            
            <!-- Средний металлический лист -->
            <rect x="14" y="16" width="28" height="18" rx="2" ry="2" 
                  fill="url(#metalGradient)" opacity="0.9" filter="url(#shadow)"/>
            
            <!-- Передний металлический лист -->
            <rect x="10" y="12" width="28" height="18" rx="2" ry="2" 
                  fill="url(#metalGradient)" filter="url(#shadow)"/>
            
            <!-- Декоративные элементы - болты -->
            <circle cx="14" cy="16" r="1.5" fill="{colors['primary']}" opacity="0.6"/>
            <circle cx="34" cy="16" r="1.5" fill="{colors['primary']}" opacity="0.6"/>
            <circle cx="14" cy="26" r="1.5" fill="{colors['primary']}" opacity="0.6"/>
            <circle cx="34" cy="26" r="1.5" fill="{colors['primary']}" opacity="0.6"/>
            
            <!-- Текст или дополнительный элемент -->
            <path d="M20 45 L32 50 L44 45 M32 50 L32 58" 
                  stroke="{colors['accent']}" stroke-width="2" fill="none" stroke-linecap="round"/>
        </svg>"""
        
        return self.save_icon("app_logo", svg, theme)
    
    def create_materials_icon(self, theme: str = "light") -> str:
        """Создает иконку материалов."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Стопка материалов -->
            <rect x="3" y="6" width="18" height="3" rx="1" fill="{colors['accent']}" opacity="0.8"/>
            <rect x="3" y="10" width="18" height="3" rx="1" fill="{colors['accent']}" opacity="0.9"/>
            <rect x="3" y="14" width="18" height="3" rx="1" fill="{colors['accent']}"/>
            
            <!-- Индикаторы -->
            <circle cx="6" cy="7.5" r="0.5" fill="{colors['background']}"/>
            <circle cx="6" cy="11.5" r="0.5" fill="{colors['background']}"/>
            <circle cx="6" cy="15.5" r="0.5" fill="{colors['background']}"/>
        </svg>"""
        
        return self.save_icon("materials", svg, theme)
    
    def create_lab_icon(self, theme: str = "light") -> str:
        """Создает иконку лаборатории."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Колба -->
            <path d="M8 2 L16 2 L16 8 L20 18 L4 18 L8 8 Z" 
                  fill="none" stroke="{colors['accent']}" stroke-width="1.5" stroke-linejoin="round"/>
            
            <!-- Жидкость в колбе -->
            <path d="M8.5 8.5 L19 17 L5 17 L8.5 8.5 Z" fill="{colors['info']}" opacity="0.6"/>
            
            <!-- Пузырьки -->
            <circle cx="10" cy="14" r="1" fill="{colors['background']}" opacity="0.8"/>
            <circle cx="14" cy="12" r="0.8" fill="{colors['background']}" opacity="0.6"/>
            <circle cx="16" cy="15" r="0.6" fill="{colors['background']}" opacity="0.7"/>
        </svg>"""
        
        return self.save_icon("lab", svg, theme)
    
    def create_reports_icon(self, theme: str = "light") -> str:
        """Создает иконку отчетов."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Документ -->
            <rect x="4" y="2" width="12" height="18" rx="1" fill="none" 
                  stroke="{colors['accent']}" stroke-width="1.5"/>
            
            <!-- Загнутый уголок -->
            <path d="M16 2 L16 6 L20 6" fill="none" stroke="{colors['accent']}" 
                  stroke-width="1.5" stroke-linejoin="round"/>
            
            <!-- Линии текста -->
            <line x1="7" y1="8" x2="13" y2="8" stroke="{colors['primary']}" stroke-width="1"/>
            <line x1="7" y1="11" x2="13" y2="11" stroke="{colors['primary']}" stroke-width="1"/>
            <line x1="7" y1="14" x2="10" y2="14" stroke="{colors['primary']}" stroke-width="1"/>
            
            <!-- График -->
            <polyline points="7,16 9,14 11,15 13,13" fill="none" 
                      stroke="{colors['success']}" stroke-width="1.5" stroke-linecap="round"/>
        </svg>"""
        
        return self.save_icon("reports", svg, theme)
    
    def create_admin_icon(self, theme: str = "light") -> str:
        """Создает иконку администрирования."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Шестеренка -->
            <path d="M12 1 L15.09 8.26 L22 9 L17 14 L18.18 21 L12 17.77 L5.82 21 L7 14 L2 9 L8.91 8.26 L12 1 Z" 
                  fill="none" stroke="{colors['accent']}" stroke-width="1.5"/>
            
            <!-- Центральный круг -->
            <circle cx="12" cy="12" r="3" fill="none" stroke="{colors['accent']}" stroke-width="1.5"/>
            
            <!-- Внутренний круг -->
            <circle cx="12" cy="12" r="1.5" fill="{colors['accent']}"/>
        </svg>"""
        
        return self.save_icon("admin", svg, theme)
    
    def create_settings_icon(self, theme: str = "light") -> str:
        """Создает иконку настроек."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Шестеренка настроек -->
            <circle cx="12" cy="12" r="3" fill="none" stroke="{colors['accent']}" stroke-width="1.5"/>
            
            <!-- Зубцы шестеренки -->
            <path d="M12 1 L12 6 M12 18 L12 23 M4.22 4.22 L7.76 7.76 M16.24 16.24 L19.78 19.78 
                     M1 12 L6 12 M18 12 L23 12 M4.22 19.78 L7.76 16.24 M16.24 7.76 L19.78 4.22" 
                  stroke="{colors['accent']}" stroke-width="1.5" stroke-linecap="round"/>
        </svg>"""
        
        return self.save_icon("settings", svg, theme)
    
    def create_search_icon(self, theme: str = "light") -> str:
        """Создает иконку поиска."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Лупа -->
            <circle cx="11" cy="11" r="8" fill="none" stroke="{colors['accent']}" stroke-width="2"/>
            <path d="M21 21 L16.65 16.65" stroke="{colors['accent']}" stroke-width="2" stroke-linecap="round"/>
        </svg>"""
        
        return self.save_icon("search", svg, theme)
    
    def create_add_icon(self, theme: str = "light") -> str:
        """Создает иконку добавления."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Плюс -->
            <circle cx="12" cy="12" r="10" fill="none" stroke="{colors['success']}" stroke-width="2"/>
            <line x1="12" y1="8" x2="12" y2="16" stroke="{colors['success']}" stroke-width="2"/>
            <line x1="8" y1="12" x2="16" y2="12" stroke="{colors['success']}" stroke-width="2"/>
        </svg>"""
        
        return self.save_icon("add", svg, theme)
    
    def create_edit_icon(self, theme: str = "light") -> str:
        """Создает иконку редактирования."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Карандаш -->
            <path d="M17 3 L21 7 L13 15 L9 15 L9 11 L17 3 Z" 
                  fill="none" stroke="{colors['warning']}" stroke-width="2" stroke-linejoin="round"/>
            <line x1="16" y1="5" x2="19" y2="8" stroke="{colors['warning']}" stroke-width="2"/>
        </svg>"""
        
        return self.save_icon("edit", svg, theme)
    
    def create_delete_icon(self, theme: str = "light") -> str:
        """Создает иконку удаления."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Корзина -->
            <polyline points="3,6 5,6 21,6" stroke="{colors['danger']}" stroke-width="2"/>
            <path d="M19 6 L19 20 A2 2 0 0 1 17 22 L7 22 A2 2 0 0 1 5 20 L5 6 M8 6 L8 4 A2 2 0 0 1 10 2 L14 2 A2 2 0 0 1 16 4 L16 6" 
                  fill="none" stroke="{colors['danger']}" stroke-width="2" stroke-linejoin="round"/>
            <line x1="10" y1="11" x2="10" y2="17" stroke="{colors['danger']}" stroke-width="2"/>
            <line x1="14" y1="11" x2="14" y2="17" stroke="{colors['danger']}" stroke-width="2"/>
        </svg>"""
        
        return self.save_icon("delete", svg, theme)
    
    def create_refresh_icon(self, theme: str = "light") -> str:
        """Создает иконку обновления."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- Стрелка обновления -->
            <polyline points="23,4 23,10 17,10" fill="none" stroke="{colors['info']}" stroke-width="2"/>
            <polyline points="1,20 1,14 7,14" fill="none" stroke="{colors['info']}" stroke-width="2"/>
            <path d="M20.49 9 A9 9 0 0 0 5.64 5.64 L1 10 M3.51 15 A9 9 0 0 0 18.36 18.36 L23 14" 
                  fill="none" stroke="{colors['info']}" stroke-width="2"/>
        </svg>"""
        
        return self.save_icon("refresh", svg, theme)
    
    def create_theme_toggle_icon(self, theme: str = "light") -> str:
        """Создает иконку переключения темы."""
        colors = self.get_theme_colors(theme)
        
        if theme == "light":
            # Иконка луны для переключения на темную тему
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                <path d="M21 12.79 A9 9 0 1 1 11.21 3 A7 7 0 0 0 21 12.79 Z" 
                      fill="{colors['accent']}" stroke="{colors['accent']}" stroke-width="1"/>
            </svg>"""
        else:
            # Иконка солнца для переключения на светлую тему
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                <circle cx="12" cy="12" r="5" fill="{colors['accent']}"/>
                <line x1="12" y1="1" x2="12" y2="3" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="12" y1="21" x2="12" y2="23" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="1" y1="12" x2="3" y2="12" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="21" y1="12" x2="23" y2="12" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="{colors['accent']}" stroke-width="2"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="{colors['accent']}" stroke-width="2"/>
            </svg>"""
        
        return self.save_icon("theme_toggle", svg, theme)
    
    def create_analytics_icon(self, theme: str = "light") -> str:
        """Создает иконку аналитики."""
        colors = self.get_theme_colors(theme)
        
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <!-- График -->
            <polyline points="3,20 7,14 11,18 15,10 21,16" fill="none" 
                      stroke="{colors['accent']}" stroke-width="2" stroke-linecap="round"/>
            
            <!-- Оси -->
            <line x1="3" y1="20" x2="21" y2="20" stroke="{colors['secondary']}" stroke-width="1"/>
            <line x1="3" y1="4" x2="3" y2="20" stroke="{colors['secondary']}" stroke-width="1"/>
            
            <!-- Точки данных -->
            <circle cx="7" cy="14" r="2" fill="{colors['accent']}"/>
            <circle cx="11" cy="18" r="2" fill="{colors['accent']}"/>
            <circle cx="15" cy="10" r="2" fill="{colors['accent']}"/>
        </svg>"""
        
        return self.save_icon("analytics", svg, theme)
    
    def save_icon(self, name: str, svg_content: str, theme: str) -> str:
        """
        Сохраняет SVG иконку в файл.
        
        Args:
            name: Название иконки
            svg_content: SVG контент
            theme: Тема (для суффикса файла)
            
        Returns:
            Путь к сохраненному файлу
        """
        filename = f"{name}_{theme}.svg"
        filepath = os.path.join(self.icons_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            return filepath
        except Exception as e:
            print(f"Ошибка сохранения иконки {filename}: {e}")
            return ""
    
    def generate_all_icons(self, themes: list = None):
        """
        Генерирует все иконки для указанных тем.
        
        Args:
            themes: Список тем (по умолчанию ['light', 'dark'])
        """
        if themes is None:
            themes = ['light', 'dark']
        
        icons = [
            'app_logo', 'materials_icon', 'lab_icon', 'reports_icon', 'admin_icon', 
            'settings_icon', 'search_icon', 'add_icon', 'edit_icon', 'delete_icon', 
            'refresh_icon', 'theme_toggle_icon', 'analytics_icon'
        ]
        
        generated = []
        
        for theme in themes:
            print(f"Генерация иконок для темы '{theme}'...")
            
            for icon in icons:
                method_name = f"create_{icon}"
                if hasattr(self, method_name):
                    try:
                        method = getattr(self, method_name)
                        filepath = method(theme)
                        if filepath:
                            generated.append(filepath)
                            print(f"  ✅ {icon}_{theme}.svg")
                        else:
                            print(f"  ❌ Ошибка создания {icon}_{theme}.svg")
                    except Exception as e:
                        print(f"  ❌ Ошибка создания {icon}_{theme}.svg: {e}")
                else:
                    print(f"  ⚠️  Метод {method_name} не найден")
        
        print(f"\nГенерация завершена. Создано {len(generated)} иконок.")
        return generated


if __name__ == "__main__":
    # Генерируем все иконки при запуске модуля
    generator = IconGenerator()
    generator.generate_all_icons() 