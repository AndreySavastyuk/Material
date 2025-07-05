"""
Компонент для предварительного просмотра протоколов.

Предоставляет интерфейс для:
- Выбора шаблона протокола
- Предварительного просмотра с реальными данными
- Экспорта в различные форматы
- Настройки параметров генерации
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QComboBox, QTextEdit, QPushButton, QLabel, QGroupBox, QSplitter,
    QCheckBox, QSpinBox, QLineEdit, QMessageBox, QProgressBar,
    QDialogButtonBox, QTabWidget, QWidget, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QTextDocument
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

from services.protocol_template_service import ProtocolTemplateService
from utils.logger import get_logger

logger = get_logger(__name__)


class ProtocolExporter(QThread):
    """Поток для экспорта протоколов в различные форматы."""
    
    progress_updated = pyqtSignal(int)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)
    
    def __init__(self, content: str, output_path: str, format_type: str):
        super().__init__()
        self.content = content
        self.output_path = output_path
        self.format_type = format_type
    
    def run(self):
        """Выполнение экспорта."""
        try:
            self.progress_updated.emit(10)
            
            if self.format_type == 'pdf':
                self._export_to_pdf()
            elif self.format_type == 'html':
                self._export_to_html()
            elif self.format_type == 'txt':
                self._export_to_txt()
            else:
                raise ValueError(f"Неподдерживаемый формат: {self.format_type}")
            
            self.progress_updated.emit(100)
            self.export_completed.emit(self.output_path)
            
        except Exception as e:
            logger.error(f"Ошибка экспорта: {e}")
            self.export_failed.emit(str(e))
    
    def _export_to_pdf(self):
        """Экспорт в PDF."""
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import black
        
        self.progress_updated.emit(30)
        
        # Регистрируем шрифт
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSans', 'resources/fonts/DejaVuSans.ttf'))
        except:
            pass  # Используем стандартный шрифт
        
        # Создаем документ
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            topMargin=1*inch,
            bottomMargin=1*inch,
            leftMargin=1*inch,
            rightMargin=1*inch
        )
        
        # Стили
        styles = getSampleStyleSheet()
        
        # Пользовательские стили
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='DejaVuSans' if 'DejaVuSans' in [f.fontName for f in pdfmetrics.getRegisteredFontNames()] else 'Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName='DejaVuSans' if 'DejaVuSans' in [f.fontName for f in pdfmetrics.getRegisteredFontNames()] else 'Helvetica'
        )
        
        self.progress_updated.emit(50)
        
        # Разбиваем содержимое на блоки
        story = []
        lines = self.content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
                continue
            
            # Заголовки
            if line.startswith('#'):
                # Убираем символы markdown
                clean_line = line.lstrip('#').strip()
                if clean_line:
                    story.append(Paragraph(clean_line, title_style))
                    story.append(Spacer(1, 12))
            else:
                # Обычный текст
                # Обрабатываем markdown разметку
                clean_line = line.replace('**', '')  # Убираем жирность
                clean_line = clean_line.replace('*', '')   # Убираем курсив
                clean_line = clean_line.replace('- ', '• ')  # Заменяем списки
                
                if clean_line:
                    story.append(Paragraph(clean_line, normal_style))
        
        self.progress_updated.emit(80)
        
        # Генерируем PDF
        doc.build(story)
        
        self.progress_updated.emit(95)
    
    def _export_to_html(self):
        """Экспорт в HTML."""
        self.progress_updated.emit(30)
        
        # Простое преобразование markdown в HTML
        html_content = self.content
        
        # Заголовки
        html_content = html_content.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)
        html_content = html_content.replace('## ', '<h2>').replace('\n', '</h2>\n', 1)
        html_content = html_content.replace('### ', '<h3>').replace('\n', '</h3>\n', 1)
        
        # Жирный текст
        html_content = html_content.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
        
        # Курсив
        html_content = html_content.replace('*', '<em>', 1).replace('*', '</em>', 1)
        
        # Списки
        html_content = html_content.replace('- ', '<li>').replace('\n', '</li>\n')
        
        # Переводы строк
        html_content = html_content.replace('\n', '<br>\n')
        
        self.progress_updated.emit(60)
        
        # Создаем полный HTML документ
        full_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Протокол испытаний</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #333;
        }}
        .protocol-content {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="protocol-content">
        {html_content}
    </div>
</body>
</html>"""
        
        self.progress_updated.emit(80)
        
        # Сохраняем в файл
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        self.progress_updated.emit(95)
    
    def _export_to_txt(self):
        """Экспорт в текстовый файл."""
        self.progress_updated.emit(50)
        
        # Очищаем от markdown разметки
        clean_content = self.content
        clean_content = clean_content.replace('# ', '').replace('## ', '').replace('### ', '')
        clean_content = clean_content.replace('**', '').replace('*', '')
        clean_content = clean_content.replace('- ', '• ')
        
        # Сохраняем в файл
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(clean_content)
        
        self.progress_updated.emit(95)


class TemplatePreview(QDialog):
    """Диалог предварительного просмотра протокола."""
    
    def __init__(self, template_service: ProtocolTemplateService, 
                 lab_request_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self.lab_request_data = lab_request_data
        self.current_template_id = None
        self.generated_content = ""
        self.export_thread = None
        
        self._setup_ui()
        self._load_templates()
        
        # Автообновление превью
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._update_preview)
    
    def _setup_ui(self):
        """Настройка интерфейса."""
        self.setWindowTitle('Предварительный просмотр протокола')
        self.setModal(True)
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Выбор шаблона
        template_group = QGroupBox('Выбор шаблона')
        template_layout = QFormLayout(template_group)
        
        self.template_combo = QComboBox()
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        template_layout.addRow('Шаблон:', self.template_combo)
        
        # Кнопка управления шаблонами
        manage_templates_btn = QPushButton('Управление шаблонами')
        manage_templates_btn.clicked.connect(self._manage_templates)
        template_layout.addRow('', manage_templates_btn)
        
        layout.addWidget(template_group)
        
        # Основная рабочая область
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - настройки
        left_panel = self._create_settings_panel()
        main_splitter.addWidget(left_panel)
        
        # Правая панель - превью
        right_panel = self._create_preview_panel()
        main_splitter.addWidget(right_panel)
        
        main_splitter.setSizes([300, 700])
        layout.addWidget(main_splitter)
        
        # Прогресс бар для экспорта
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.export_btn = QPushButton('Экспортировать')
        self.export_btn.clicked.connect(self._export_protocol)
        self.export_btn.setEnabled(False)
        buttons_layout.addWidget(self.export_btn)
        
        self.print_btn = QPushButton('Печать')
        self.print_btn.clicked.connect(self._print_protocol)
        self.print_btn.setEnabled(False)
        buttons_layout.addWidget(self.print_btn)
        
        buttons_layout.addStretch()
        
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def _create_settings_panel(self) -> QWidget:
        """Создание панели настроек."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Настройки генерации
        generation_group = QGroupBox('Настройки генерации')
        generation_layout = QFormLayout(generation_group)
        
        self.calculate_formulas_cb = QCheckBox('Выполнять расчеты формул')
        self.calculate_formulas_cb.setChecked(True)
        self.calculate_formulas_cb.stateChanged.connect(self._on_settings_changed)
        generation_layout.addRow('', self.calculate_formulas_cb)
        
        self.include_raw_data_cb = QCheckBox('Включить исходные данные')
        self.include_raw_data_cb.setChecked(False)
        self.include_raw_data_cb.stateChanged.connect(self._on_settings_changed)
        generation_layout.addRow('', self.include_raw_data_cb)
        
        layout.addWidget(generation_group)
        
        # Настройки экспорта
        export_group = QGroupBox('Настройки экспорта')
        export_layout = QFormLayout(export_group)
        
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(['PDF', 'HTML', 'TXT'])
        export_layout.addRow('Формат вывода:', self.output_format_combo)
        
        self.output_filename_edit = QLineEdit()
        self.output_filename_edit.setText('protocol')
        export_layout.addRow('Имя файла:', self.output_filename_edit)
        
        layout.addWidget(export_group)
        
        # Информация о заявке
        info_group = QGroupBox('Информация о заявке')
        info_layout = QFormLayout(info_group)
        
        info_layout.addRow('Номер заявки:', 
                          QLabel(self.lab_request_data.get('request_number', 'Не указан')))
        info_layout.addRow('Материал:', 
                          QLabel(self.lab_request_data.get('material', 'Не указан')))
        info_layout.addRow('Статус:', 
                          QLabel(self.lab_request_data.get('status', 'Не указан')))
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        return widget
    
    def _create_preview_panel(self) -> QWidget:
        """Создание панели превью."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Заголовок
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel('Предварительный просмотр'))
        
        self.refresh_btn = QPushButton('Обновить')
        self.refresh_btn.clicked.connect(self._update_preview)
        title_layout.addWidget(self.refresh_btn)
        
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Область превью
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont('Courier New', 10))
        layout.addWidget(self.preview_text)
        
        # Сообщения об ошибках
        self.error_label = QLabel()
        self.error_label.setStyleSheet('color: red; font-weight: bold;')
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        
        return widget
    
    def _load_templates(self):
        """Загрузка списка шаблонов."""
        try:
            templates = self.template_service.get_all_templates()
            self.template_combo.clear()
            
            for template in templates:
                self.template_combo.addItem(template['name'], template['id'])
            
            # Выбираем шаблон по умолчанию
            for i, template in enumerate(templates):
                if template.get('is_default', False):
                    self.template_combo.setCurrentIndex(i)
                    break
            
            if self.template_combo.count() > 0:
                self._update_preview()
                
        except Exception as e:
            logger.error(f"Ошибка загрузки шаблонов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки шаблонов: {e}")
    
    def _on_template_changed(self):
        """Обработка изменения выбранного шаблона."""
        self.current_template_id = self.template_combo.currentData()
        self._update_preview()
    
    def _on_settings_changed(self):
        """Обработка изменения настроек."""
        # Обновляем превью с задержкой
        self.preview_timer.start(500)
    
    def _update_preview(self):
        """Обновление превью протокола."""
        if not self.current_template_id:
            self.preview_text.clear()
            self.export_btn.setEnabled(False)
            self.print_btn.setEnabled(False)
            return
        
        try:
            # Подготавливаем данные для генерации
            context_data = self._prepare_context_data()
            
            # Генерируем протокол
            calculate_formulas = self.calculate_formulas_cb.isChecked()
            self.generated_content = self.template_service.generate_protocol(
                self.current_template_id, context_data, calculate_formulas
            )
            
            # Отображаем в превью
            self.preview_text.setPlainText(self.generated_content)
            
            # Включаем кнопки экспорта
            self.export_btn.setEnabled(True)
            self.print_btn.setEnabled(True)
            
            # Скрываем ошибки
            self.error_label.setVisible(False)
            
        except Exception as e:
            logger.error(f"Ошибка генерации превью: {e}")
            self.error_label.setText(f"Ошибка генерации: {e}")
            self.error_label.setVisible(True)
            self.export_btn.setEnabled(False)
            self.print_btn.setEnabled(False)
    
    def _prepare_context_data(self) -> Dict[str, Any]:
        """Подготовка данных для генерации протокола."""
        context = dict(self.lab_request_data)
        
        # Добавляем системные переменные
        from datetime import datetime
        context.update({
            'report_date': datetime.now().strftime('%d.%m.%Y'),
            'report_time': datetime.now().strftime('%H:%M'),
            'operator_name': 'Текущий пользователь',  # TODO: получать из контекста
            'temperature': 20,
            'humidity': 50
        })
        
        # Включаем исходные данные если нужно
        if self.include_raw_data_cb.isChecked():
            context['raw_data'] = self.lab_request_data
        
        return context
    
    def _export_protocol(self):
        """Экспорт протокола в файл."""
        if not self.generated_content:
            QMessageBox.warning(self, "Ошибка", "Нет данных для экспорта")
            return
        
        try:
            # Определяем путь для сохранения
            format_type = self.output_format_combo.currentText().lower()
            filename = self.output_filename_edit.text().strip()
            if not filename:
                filename = f"protocol_{self.lab_request_data.get('request_number', 'unknown')}"
            
            # Папка для сохранения отчетов
            output_dir = Path("lab_reports")
            output_dir.mkdir(exist_ok=True)
            
            output_path = output_dir / f"{filename}.{format_type}"
            
            # Запускаем экспорт в отдельном потоке
            self.export_thread = ProtocolExporter(
                self.generated_content, str(output_path), format_type
            )
            
            self.export_thread.progress_updated.connect(self.progress_bar.setValue)
            self.export_thread.export_completed.connect(self._on_export_completed)
            self.export_thread.export_failed.connect(self._on_export_failed)
            
            # Показываем прогресс
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.export_btn.setEnabled(False)
            
            # Запускаем экспорт
            self.export_thread.start()
            
        except Exception as e:
            logger.error(f"Ошибка подготовки экспорта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {e}")
    
    def _on_export_completed(self, output_path: str):
        """Обработка завершения экспорта."""
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        
        QMessageBox.information(
            self, "Успех", 
            f"Протокол успешно экспортирован в:\n{output_path}"
        )
    
    def _on_export_failed(self, error_message: str):
        """Обработка ошибки экспорта."""
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        
        QMessageBox.critical(
            self, "Ошибка экспорта", 
            f"Не удалось экспортировать протокол:\n{error_message}"
        )
    
    def _print_protocol(self):
        """Печать протокола."""
        if not self.generated_content:
            QMessageBox.warning(self, "Ошибка", "Нет данных для печати")
            return
        
        try:
            # Создаем принтер
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            
            # Показываем диалог печати
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec_() == QPrintDialog.Accepted:
                # Создаем документ для печати
                document = QTextDocument()
                document.setPlainText(self.generated_content)
                
                # Печатаем
                document.print_(printer)
                
                QMessageBox.information(self, "Успех", "Протокол отправлен на печать")
                
        except Exception as e:
            logger.error(f"Ошибка печати: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка печати: {e}")
    
    def _manage_templates(self):
        """Открытие менеджера шаблонов."""
        from gui.lab.template_editor import TemplateManager
        
        dialog = TemplateManager(self.template_service, self)
        if dialog.exec_() == QDialog.Accepted:
            # Обновляем список шаблонов
            current_template_id = self.template_combo.currentData()
            self._load_templates()
            
            # Восстанавливаем выбранный шаблон если возможно
            if current_template_id:
                for i in range(self.template_combo.count()):
                    if self.template_combo.itemData(i) == current_template_id:
                        self.template_combo.setCurrentIndex(i)
                        break
    
    def closeEvent(self, event):
        """Обработка закрытия диалога."""
        if self.export_thread and self.export_thread.isRunning():
            self.export_thread.terminate()
            self.export_thread.wait()
        
        super().closeEvent(event)


def show_protocol_preview(template_service: ProtocolTemplateService, 
                         lab_request_data: Dict[str, Any], 
                         parent=None) -> None:
    """
    Удобная функция для показа превью протокола.
    
    Args:
        template_service: Сервис для работы с шаблонами
        lab_request_data: Данные лабораторной заявки
        parent: Родительский виджет
    """
    dialog = TemplatePreview(template_service, lab_request_data, parent)
    dialog.exec_() 