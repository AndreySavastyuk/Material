from PyQt5.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QDesktopWidget, QMenu, QStyle, QDateEdit,
    QComboBox, QLineEdit, QHBoxLayout, QDialog
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QDate
from PyQt5.QtGui import QColor

from db.database import Database
from services.materials_service import MaterialsService
from repositories.materials_repository import MaterialsRepository
from utils.async_operations import MaterialsLoadWorker, MaterialsSearchWorker, ProgressWidget, DebounceTimer
from gui.dialogs import AddMaterialDialog
from gui.admin.suppliers import SuppliersAdmin
from gui.admin.grades import GradesAdmin
from gui.admin.rolling_types import RollingTypesAdmin
from gui.admin.test_scenarios import TestScenariosAdmin
from gui.admin.moderation import ModerationDialog
from gui.otk.otk_window import OtkWindow
from gui.lab.lab_window import LabWindow
from gui.audit.audit_window import AuditWindow
from gui.settings.settings_window import SettingsWindow
from gui.defects.defects_window import DefectsWindow
from logger import log_event

class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.db = Database()
        self.db.connect()
        self.db.docs_root = r"D:\mes"
        
        # Инициализация сервиса материалов
        self.materials_repo = MaterialsRepository(self.db.conn, self.db.docs_root)
        self.materials_service = MaterialsService(self.materials_repo)
        
        # Асинхронные операции
        self.current_load_worker = None
        self.current_search_worker = None
        
        # Debounce для поиска
        self.search_debounce = DebounceTimer(delay_ms=500)

        self.setWindowTitle('Система контроля материалов')
        geom = QDesktopWidget().screenGeometry()
        self.resize(int(geom.width() * 0.8), int(geom.height() * 0.7))

        self._create_menus()
        self._build()
        self._load_async()  # Заменяем на асинхронную загрузку

        self._last_count = 0  # Инициализируем нулем, обновим после первой загрузки
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_poll)
        self._refresh_timer.start(5000)

    def _create_menus(self):
        menubar = self.menuBar()
        settings_menu = menubar.addMenu('Настройки')
        settings_menu.addAction('Настройки приложения', lambda: SettingsWindow(self).exec_())
        if self.user.get('role') == 'Администратор':
            admin_menu = menubar.addMenu('Справочники')
            admin_menu.addAction('Поставщики', lambda: SuppliersAdmin(self).exec_())
            admin_menu.addAction('Марки', lambda: GradesAdmin(self).exec_())
            admin_menu.addAction('Виды проката', lambda: RollingTypesAdmin(self).exec_())
            admin_menu.addAction('Модерация удаления', lambda: ModerationDialog(self).exec_())
            admin_menu.addAction('Журнал действий', lambda: AuditWindow(self).exec_())
            admin_menu.addAction('Сценарии испытаний', lambda: TestScenariosAdmin(self).exec_())
        modules_menu = menubar.addMenu('Модули')
        modules_menu.addAction('ОТК', lambda: self._open_otk())
        modules_menu.addAction('Лаборатория', lambda: self._open_lab())
        modules_menu.addAction('Журнал дефектов', lambda: self.open_defects())

    def _build(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        # Прогресс виджет для асинхронных операций
        self.progress_widget = ProgressWidget()
        layout.addWidget(self.progress_widget)

        # Фильтр поиска
        flt_layout = QHBoxLayout()
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText('Введите 2+ символа для поиска…')
        flt_layout.addWidget(self.le_filter)
        layout.addLayout(flt_layout)
        # Используем debounce для поиска
        self.le_filter.textChanged.connect(self._on_search_text_changed_debounced)

        # Действия
        btn_add = QPushButton('Добавить материал')
        btn_add.clicked.connect(self._add)
        btn_refresh = QPushButton('Обновить')
        btn_refresh.clicked.connect(self._manual_refresh_async)  # Используем асинхронное обновление
        btn_defects = QPushButton('Журнал дефектов')
        btn_defects.clicked.connect(self.open_defects)
        layout.addWidget(btn_add)
        layout.addWidget(btn_refresh)
        layout.addWidget(btn_defects)

        # Таблица
        self.tbl = QTableWidget()
        layout.addWidget(self.tbl)
        self.tbl.setColumnCount(14)
        self.tbl.setHorizontalHeaderLabels([
            'Дата прихода', 'Поставщик', 'Номер заказа', 'Марка',
            'Вид проката', 'Размер', 'Сертификат №', 'Дата серт.',
            'Партия', 'Плавка', 'Длина (мм)', 'Вес (кг)',
            'Заметки ОТК', 'ППСД'
        ])
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._show_context_menu)

        self.setCentralWidget(central)

    def _load_async(self):
        """Асинхронная загрузка материалов."""
        try:
            # Отменяем предыдущую операцию загрузки если она выполняется
            if self.current_load_worker and self.current_load_worker.isRunning():
                self.current_load_worker.cancel()
                self.current_load_worker.wait()
            
            # Создаем новый воркер
            self.current_load_worker = MaterialsLoadWorker(self.materials_service, self)
            
            # Подключаем сигналы
            self.current_load_worker.result_ready.connect(self._on_materials_loaded)
            self.current_load_worker.error_occurred.connect(self._on_load_error)
            
            # Запускаем прогресс виджет
            self.progress_widget.start_operation(self.current_load_worker)
            
            # Запускаем операцию
            self.current_load_worker.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка запуска загрузки: {str(e)}")

    def _search_async(self, search_text: str):
        """Асинхронный поиск материалов."""
        try:
            # Отменяем предыдущую операцию поиска если она выполняется
            if self.current_search_worker and self.current_search_worker.isRunning():
                self.current_search_worker.cancel()
                self.current_search_worker.wait()
            
            # Создаем новый воркер
            self.current_search_worker = MaterialsSearchWorker(self.materials_service, search_text, self)
            
            # Подключаем сигналы
            self.current_search_worker.result_ready.connect(self._on_search_results)
            self.current_search_worker.error_occurred.connect(self._on_search_error)
            
            # Запускаем прогресс виджет
            self.progress_widget.start_operation(self.current_search_worker)
            
            # Запускаем операцию
            self.current_search_worker.start()
            
        except Exception as e:
            QMessageBox.warning(self, "Ошибка поиска", f"Ошибка запуска поиска: {str(e)}")

    def _on_materials_loaded(self, materials: list):
        """Обработчик успешной загрузки материалов."""
        self._update_table_with_materials(materials)
        self._last_count = len(materials)

    def _on_search_results(self, materials: list):
        """Обработчик результатов поиска."""
        self._update_table_with_materials(materials)

    def _on_load_error(self, error: Exception):
        """Обработчик ошибки загрузки."""
        QMessageBox.critical(self, "Ошибка загрузки", f"Ошибка загрузки материалов: {str(error)}")

    def _on_search_error(self, error: Exception):
        """Обработчик ошибки поиска."""
        QMessageBox.warning(self, "Ошибка поиска", f"Ошибка поиска материалов: {str(error)}")

    def _update_table_with_materials(self, materials: list):
        """Обновляет таблицу с материалами."""
        try:
            self.tbl.setRowCount(len(materials))
            for i, r in enumerate(materials):
                # Используем отформатированные данные
                vals = [
                    r.get('arrival_date_display', r.get('arrival_date', '')),
                    r.get('supplier', ''),
                    r.get('order_num', ''),
                    r.get('grade', ''),
                    r.get('rolling_type', ''),
                    r.get('size', ''),
                    r.get('cert_num', ''),
                    r.get('cert_date_display', r.get('cert_date', '')),
                    r.get('batch', ''),
                    r.get('heat_num', ''),
                    r.get('volume_length_display', '0'),
                    r.get('volume_weight_display', '0'),
                    r.get('otk_remarks_display', ''),
                    r.get('needs_lab_display', '')
                ]
                
                for j, v in enumerate(vals):
                    item = QTableWidgetItem(str(v))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.tbl.setItem(i, j, item)
                
                # Выделяем помеченные на удаление
                if r.get('to_delete'):
                    for col in range(self.tbl.columnCount()):
                        itm = self.tbl.item(i, col)
                        itm.setBackground(QColor(200, 200, 200, 128))
                        itm.setForeground(QColor(0, 0, 0, 153))
                    self.tbl.item(i, 0).setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
                    
            self.tbl.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления таблицы: {str(e)}")

    def _on_search_text_changed_debounced(self, text: str):
        """Обработчик изменения текста поиска с debounce."""
        self.search_debounce.debounce(self._search_async, text.strip())

    def _manual_refresh_async(self):
        """Асинхронное ручное обновление данных."""
        try:
            # Очищаем кеш справочников
            self.materials_service.clear_cache()
            # Запускаем асинхронную загрузку
            self._load_async()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления: {str(e)}")

    def _load(self, rows=None):
        """Загружает данные материалов в таблицу (оставляем для обратной совместимости)."""
        if rows is not None:
            self._update_table_with_materials(rows)
        else:
            # Используем асинхронную загрузку
            self._load_async()

    def _on_search_text_changed(self, text):
        """Обрабатывает изменение текста поиска (старый метод, оставляем для совместимости)."""
        self._on_search_text_changed_debounced(text)

    def _on_poll(self):
        """Проверяет изменения в данных (периодический опрос)."""
        try:
            # Проверяем асинхронно только если нет активных операций
            if not self._is_loading_active():
                curr = len(self.materials_service.get_all_materials())
                if curr != self._last_count:
                    # Можно подсветить кнопку Обновить или показать уведомление
                    # Автоматически не обновляем чтобы не прерывать работу пользователя
                    pass
                self._last_count = curr
                
        except Exception as e:
            # Логируем ошибки опроса, но не показываем пользователю
            pass

    def _is_loading_active(self) -> bool:
        """Проверяет, выполняется ли сейчас загрузка или поиск."""
        return ((self.current_load_worker and self.current_load_worker.isRunning()) or
                (self.current_search_worker and self.current_search_worker.isRunning()))

    def _show_context_menu(self, pos: QPoint):
        """Показывает контекстное меню для материала."""
        try:
            row = self.tbl.rowAt(pos.y())
            if row < 0:
                return
            
            # Получаем материалы синхронно для контекстного меню
            # (это быстрая операция, не требует асинхронности)
            materials = self.materials_service.get_all_materials()
            if row >= len(materials):
                return
                
            mat = materials[row]
            material_id = mat['id']
            
            menu = QMenu(self)
            text = 'Снять метку' if mat.get('to_delete') else 'Пометить на удаление'
            act = menu.addAction(text)
            
            if menu.exec_(self.tbl.viewport().mapToGlobal(pos)) == act:
                user_login = self.user.get('login', 'unknown')
                
                if mat.get('to_delete'):
                    success = self.materials_service.unmark_for_deletion(material_id, user_login)
                    if success:
                        log_event(self.user, 'unmark', material_id, 'Снята метка')
                        QMessageBox.information(self, "Успех", "Метка удаления снята")
                    else:
                        QMessageBox.warning(self, "Ошибка", "Не удалось снять метку")
                else:
                    success = self.materials_service.mark_for_deletion(material_id, user_login)
                    if success:
                        log_event(self.user, 'mark', material_id, 'Помечена на удаление')
                        QMessageBox.information(self, "Успех", "Материал помечен на удаление")
                    else:
                        QMessageBox.warning(self, "Ошибка", "Не удалось пометить на удаление")
                
                # Обновляем таблицу асинхронно
                self._load_async()
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка в контекстном меню: {str(e)}")

    def _add(self):
        """Открывает диалог добавления материала."""
        try:
            dlg = AddMaterialDialog(self)
            dlg.setMinimumSize(800, 600)
            if dlg.exec_() == QDialog.Accepted:
                data = dlg.data()
                
                # Создаем материал через сервис
                material_id = self.materials_service.create(data)
                
                log_event(self.user, 'add_material', material_id, str(data))
                QMessageBox.information(self, 'Готово', f'Материал добавлен с ID: {material_id}')
                
                # Обновляем таблицу асинхронно
                self._load_async()
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка добавления материала: {str(e)}")

    def _open_otk(self):
        """Открывает модуль ОТК."""
        OtkWindow(self).exec_()

    def _open_lab(self):
        """Открывает модуль лаборатории."""
        LabWindow(self).show()

    def open_defects(self):
        """Открывает журнал дефектов."""
        DefectsWindow(self).exec_()

    def closeEvent(self, event):
        """Обрабатывает закрытие окна."""
        # Отменяем все активные операции
        if self.current_load_worker and self.current_load_worker.isRunning():
            self.current_load_worker.cancel()
            self.current_load_worker.wait()
            
        if self.current_search_worker and self.current_search_worker.isRunning():
            self.current_search_worker.cancel()
            self.current_search_worker.wait()
            
        self.db.close()
        super().closeEvent(event)
