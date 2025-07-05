"""
Главное окно приложения с интеграцией системы ролей и прав доступа.

Этот модуль демонстрирует интеграцию системы авторизации в GUI:
- Проверка прав перед показом элементов интерфейса
- Динамическое создание меню на основе прав пользователя
- Контроль доступа к операциям
- Аудит действий пользователей
"""

from PyQt5.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QDesktopWidget, QMenu, QStyle, QDateEdit,
    QComboBox, QLineEdit, QHBoxLayout, QDialog, QLabel
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QDate
from PyQt5.QtGui import QColor, QIcon
from typing import Dict, List, Optional

from db.database import Database
from services.authorization_service import AuthorizationService
from services.materials_service import MaterialsService
from repositories.materials_repository import MaterialsRepository
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
from utils.decorators import require_permission, audit_action
from utils.exceptions import InsufficientPermissionsError
from logger import log_event


class RoleBasedMainWindow(QMainWindow):
    """
    Главное окно приложения с интеграцией системы ролей и прав доступа.
    
    Особенности:
    - Динамическое создание меню на основе прав пользователя
    - Проверка прав перед выполнением операций
    - Скрытие элементов интерфейса при отсутствии прав
    - Аудит действий пользователей
    """
    
    def __init__(self, user: Dict, auth_service: 'AuthorizationService' = None):
        """
        Инициализация главного окна.
        
        Args:
            user: Данные пользователя с полями id, login, role, name
            auth_service: Сервис авторизации (если не передан, создается новый)
        """
        super().__init__()
        
        # Сохраняем данные пользователя
        self.user = user
        self.current_user_id = user['id']
        
        # Инициализируем сервисы
        if auth_service:
            self.auth_service = auth_service
            self.db = auth_service.db
        else:
            self.db = Database()
            self.db.connect()
            self.auth_service = AuthorizationService(self.db)
        
        self.db.docs_root = r"D:\mes"
        
        # Инициализация сервиса материалов
        self.materials_repo = MaterialsRepository(self.db.conn, self.db.docs_root)
        self.materials_service = MaterialsService(self.materials_repo)
        
        # Загружаем права пользователя
        self.user_permissions = self._load_user_permissions()
        self.user_roles = self._load_user_roles()
        
        # Настройка окна
        self.setWindowTitle('Система контроля материалов')
        geom = QDesktopWidget().screenGeometry()
        self.resize(int(geom.width() * 0.8), int(geom.height() * 0.7))
        
        # Создание интерфейса
        self._create_menus()
        self._build()
        self._load()
        
        # Таймер обновления
        self._last_count = len(self.materials_service.get_all_materials())
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_poll)
        self._refresh_timer.start(5000)
        
        # Система автоматического logout
        self._setup_auto_logout()
        
        # Показываем информацию о пользователе
        self._show_user_info()

    def _load_user_permissions(self) -> Dict[str, bool]:
        """
        Загружает права пользователя и создает словарь для быстрой проверки.
        
        Returns:
            Словарь {permission_name: True}
        """
        try:
            permissions = self.db.get_user_permissions(self.current_user_id)
            return {p['name']: True for p in permissions}
        except Exception as e:
            QMessageBox.warning(
                self, 
                'Ошибка загрузки прав', 
                f'Не удалось загрузить права пользователя: {e}'
            )
            return {}

    def _load_user_roles(self) -> List[str]:
        """
        Загружает роли пользователя.
        
        Returns:
            Список имен ролей
        """
        try:
            roles = self.db.get_user_roles(self.current_user_id)
            return [r['name'] for r in roles]
        except Exception as e:
            QMessageBox.warning(
                self, 
                'Ошибка загрузки ролей', 
                f'Не удалось загрузить роли пользователя: {e}'
            )
            return []

    def has_permission(self, permission: str) -> bool:
        """
        Проверяет наличие права у текущего пользователя.
        
        Args:
            permission: Название права
            
        Returns:
            True если право есть
        """
        return self.user_permissions.get(permission, False)

    def require_permission_gui(self, permission: str, action_name: str = "выполнить операцию") -> bool:
        """
        Проверяет право и показывает сообщение об ошибке если его нет.
        
        Args:
            permission: Требуемое право
            action_name: Название действия для сообщения об ошибке
            
        Returns:
            True если право есть, False в противном случае
        """
        if not self.has_permission(permission):
            QMessageBox.warning(
                self,
                'Недостаточно прав',
                f'У вас нет прав для "{action_name}".\n'
                f'Необходимо право: {permission}\n\n'
                f'Обратитесь к администратору для получения доступа.'
            )
            return False
        return True

    def _show_user_info(self):
        """Показывает информацию о текущем пользователе в статусной строке."""
        user_info = f"Пользователь: {self.user['name']} ({self.user['login']})"
        roles_info = f"Роли: {', '.join(self.user_roles)}" if self.user_roles else "Роли: не назначены"
        permissions_count = len(self.user_permissions)
        
        status_text = f"{user_info} | {roles_info} | Прав: {permissions_count}"
        self.statusBar().showMessage(status_text)

    def _setup_auto_logout(self):
        """Настраивает систему автоматического logout."""
        # Настройки таймаута (в минутах)
        self.inactivity_timeout = 30  # 30 минут неактивности
        self.warning_timeout = 5      # 5 минут до логаута показать предупреждение
        
        # Таймер неактивности
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.timeout.connect(self._on_inactivity_timeout)
        self._inactivity_timer.setSingleShot(True)
        
        # Таймер предупреждения
        self._warning_timer = QTimer(self)
        self._warning_timer.timeout.connect(self._on_warning_timeout)
        self._warning_timer.setSingleShot(True)
        
        # Диалог предупреждения
        self._warning_dialog = None
        
        # Устанавливаем фильтр событий для отслеживания активности
        self.installEventFilter(self)
        
        # Запускаем таймер неактивности
        self._reset_inactivity_timer()

    def _reset_inactivity_timer(self):
        """Сбрасывает таймер неактивности при активности пользователя."""
        # Останавливаем все таймеры
        self._inactivity_timer.stop()
        self._warning_timer.stop()
        
        # Закрываем диалог предупреждения если он открыт
        if self._warning_dialog:
            self._warning_dialog.close()
            self._warning_dialog = None
        
        # Запускаем таймер неактивности
        timeout_ms = (self.inactivity_timeout - self.warning_timeout) * 60 * 1000
        self._inactivity_timer.start(timeout_ms)

    def _on_inactivity_timeout(self):
        """Вызывается при истечении времени неактивности."""
        # Запускаем таймер предупреждения
        warning_ms = self.warning_timeout * 60 * 1000
        self._warning_timer.start(warning_ms)
        
        # Показываем диалог предупреждения
        self._show_logout_warning()

    def _on_warning_timeout(self):
        """Вызывается при истечении времени предупреждения."""
        # Закрываем диалог предупреждения
        if self._warning_dialog:
            self._warning_dialog.close()
            self._warning_dialog = None
        
        # Выполняем автоматический logout
        self._perform_auto_logout()

    def _show_logout_warning(self):
        """Показывает предупреждение о скором logout."""
        if self._warning_dialog:
            return
            
        from PyQt5.QtWidgets import QProgressBar
        
        # Создаем диалог предупреждения
        self._warning_dialog = QDialog(self)
        self._warning_dialog.setWindowTitle('Предупреждение о выходе')
        self._warning_dialog.setModal(True)
        self._warning_dialog.setFixedSize(400, 200)
        
        layout = QVBoxLayout()
        
        # Текст предупреждения
        warning_text = QLabel(
            f'Вы будете автоматически выведены из системы\n'
            f'через {self.warning_timeout} минут из-за неактивности.\n\n'
            f'Нажмите "Остаться" для продолжения работы.'
        )
        warning_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning_text)
        
        # Прогресс-бар для отображения оставшегося времени
        self._logout_progress = QProgressBar()
        self._logout_progress.setMaximum(self.warning_timeout * 60)
        self._logout_progress.setValue(self.warning_timeout * 60)
        layout.addWidget(self._logout_progress)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        stay_button = QPushButton('Остаться в системе')
        stay_button.clicked.connect(self._cancel_auto_logout)
        stay_button.setDefault(True)
        
        logout_button = QPushButton('Выйти сейчас')
        logout_button.clicked.connect(self._perform_auto_logout)
        
        button_layout.addWidget(stay_button)
        button_layout.addWidget(logout_button)
        layout.addLayout(button_layout)
        
        self._warning_dialog.setLayout(layout)
        
        # Таймер для обновления прогресс-бара
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_logout_countdown)
        self._countdown_timer.start(1000)  # Обновляем каждую секунду
        
        self._warning_dialog.show()
        self._warning_dialog.raise_()
        self._warning_dialog.activateWindow()

    def _update_logout_countdown(self):
        """Обновляет прогресс-бар отсчета до logout."""
        if not self._warning_dialog or not self._logout_progress:
            return
            
        current_value = self._logout_progress.value()
        if current_value > 0:
            self._logout_progress.setValue(current_value - 1)
            
            # Обновляем текст с оставшимся временем
            remaining_seconds = current_value - 1
            remaining_minutes = remaining_seconds // 60
            remaining_seconds = remaining_seconds % 60
            
            if remaining_minutes > 0:
                time_text = f"{remaining_minutes}:{remaining_seconds:02d}"
            else:
                time_text = f"{remaining_seconds} сек"
                
            self._logout_progress.setFormat(f"Осталось: {time_text}")
        else:
            self._countdown_timer.stop()

    def _cancel_auto_logout(self):
        """Отменяет автоматический logout."""
        # Сбрасываем таймер неактивности
        self._reset_inactivity_timer()
        
        # Закрываем диалог предупреждения
        if self._warning_dialog:
            self._warning_dialog.close()
            self._warning_dialog = None
        
        # Логируем отмену автоматического выхода
        log_event(self.user, 'cancel_auto_logout', 0, f'Пользователь {self.user["login"]} отменил автоматический выход')

    def _perform_auto_logout(self):
        """Выполняет автоматический logout."""
        try:
            # Инвалидируем сессию
            session_token = self.user.get('session_token')
            if session_token:
                self.auth_service.logout_user(self.current_user_id, session_token)
                
            # Логируем автоматический выход
            log_event(self.user, 'auto_logout', 0, f'Автоматический выход пользователя {self.user["login"]} из-за неактивности')
            
            # Показываем сообщение пользователю
            QMessageBox.information(
                self,
                'Автоматический выход',
                'Сессия завершена из-за длительного бездействия.\n'
                'Пожалуйста, войдите в систему заново.'
            )
            
            # Закрываем приложение
            self.close()
            
        except Exception as e:
            log_event(self.user, 'app_close_error', 0, f"Ошибка при автоматическом выходе: {e}")
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при автоматическом выходе: {e}')

    def eventFilter(self, obj, event):
        """Фильтр событий для отслеживания активности пользователя."""
        # Отслеживаем события, указывающие на активность пользователя
        if event.type() in [
            event.MouseButtonPress,
            event.MouseButtonRelease,
            event.MouseMove,
            event.KeyPress,
            event.KeyRelease,
            event.Wheel,
            event.TouchBegin,
            event.TouchEnd,
            event.TouchUpdate
        ]:
            # Сбрасываем таймер неактивности при активности
            self._reset_inactivity_timer()
        
        return super().eventFilter(obj, event)

    def _create_menus(self):
        """Создает меню с проверкой прав доступа."""
        menubar = self.menuBar()
        
        # Меню настроек (доступно всем)
        settings_menu = menubar.addMenu('Настройки')
        settings_menu.addAction('Настройки приложения', lambda: self._open_settings())
        
        # Административное меню (только для пользователей с правами администратора)
        if self._has_admin_permissions():
            admin_menu = menubar.addMenu('Справочники')
            
            if self.has_permission('suppliers.view'):
                admin_menu.addAction('Поставщики', lambda: self._open_suppliers_admin())
            
            if self.has_permission('admin.settings'):
                admin_menu.addAction('Марки', lambda: self._open_grades_admin())
                admin_menu.addAction('Виды проката', lambda: self._open_rolling_types_admin())
            
            if self.has_permission('admin.users'):
                admin_menu.addAction('Модерация удаления', lambda: self._open_moderation())
            
            if self.has_permission('admin.logs'):
                admin_menu.addAction('Журнал действий', lambda: self._open_audit())
            
            if self.has_permission('lab.edit'):
                admin_menu.addAction('Сценарии испытаний', lambda: self._open_test_scenarios())
        
        # Меню модулей (с проверкой прав)
        modules_menu = menubar.addMenu('Модули')
        
        if self.has_permission('quality.view'):
            modules_menu.addAction('ОТК', lambda: self._open_otk())
        
        if self.has_permission('lab.view'):
            modules_menu.addAction('Лаборатория', lambda: self._open_lab())
        
        if self.has_permission('materials.view'):
            modules_menu.addAction('Журнал дефектов', lambda: self._open_defects())
        
        # Меню пользователя
        user_menu = menubar.addMenu('Пользователь')
        user_menu.addAction('Сменить пароль', lambda: self._change_password())
        user_menu.addAction('Мои права', lambda: self._show_my_permissions())
        user_menu.addAction('Выход', lambda: self.close())

    def _has_admin_permissions(self) -> bool:
        """Проверяет, есть ли у пользователя хотя бы одно административное право."""
        admin_permissions = [
            'admin.users', 'admin.roles', 'admin.permissions', 
            'admin.settings', 'admin.backup', 'admin.logs'
        ]
        return any(self.has_permission(perm) for perm in admin_permissions)

    def _build(self):
        """Создает основной интерфейс с проверкой прав."""
        central = QWidget()
        layout = QVBoxLayout(central)

        # Фильтр поиска (доступен всем, кто может просматривать материалы)
        if self.has_permission('materials.view'):
            flt_layout = QHBoxLayout()
            self.le_filter = QLineEdit()
            self.le_filter.setPlaceholderText('Введите 2+ символа для поиска…')
            flt_layout.addWidget(self.le_filter)
            layout.addLayout(flt_layout)
            self.le_filter.textChanged.connect(self._on_search_text_changed)
        else:
            # Показываем сообщение о недостатке прав
            no_access_label = QLabel('У вас нет прав для просмотра материалов')
            no_access_label.setAlignment(Qt.AlignCenter)
            no_access_label.setStyleSheet('color: red; font-size: 14px; padding: 20px;')
            layout.addWidget(no_access_label)
            self.setCentralWidget(central)
            return

        # Кнопки действий (с проверкой прав)
        buttons_layout = QHBoxLayout()
        
        if self.has_permission('materials.create'):
            btn_add = QPushButton('Добавить материал')
            btn_add.clicked.connect(self._add_material)
            buttons_layout.addWidget(btn_add)
        
        if self.has_permission('materials.view'):
            btn_refresh = QPushButton('Обновить')
            btn_refresh.clicked.connect(self._manual_refresh)
            buttons_layout.addWidget(btn_refresh)
        
        if self.has_permission('materials.view'):
            btn_defects = QPushButton('Журнал дефектов')
            btn_defects.clicked.connect(self._open_defects)
            buttons_layout.addWidget(btn_defects)
        
        if buttons_layout.count() > 0:
            layout.addLayout(buttons_layout)

        # Таблица материалов
        if self.has_permission('materials.view'):
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

    def _load(self, rows=None):
        """Загружает данные в таблицу (только если есть права на просмотр)."""
        if not self.has_permission('materials.view'):
            return
            
        try:
            if rows is None:
                # Получаем материалы через сервис с форматированием
                materials = self.materials_service.get_all_materials()
                rows = self.materials_service.format_materials_for_display(materials)
            
            self.tbl.setRowCount(len(rows))
            
            for i, r in enumerate(rows):
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
                
                # Помечаем удаленные материалы
                if r.get('to_delete'):
                    for col in range(self.tbl.columnCount()):
                        itm = self.tbl.item(i, col)
                        itm.setBackground(QColor(200, 200, 200, 128))
                        itm.setForeground(QColor(0, 0, 0, 153))
                    self.tbl.item(i, 0).setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            
            self.tbl.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при загрузке данных: {e}')

    def _on_search_text_changed(self, text: str):
        """Обработчик изменения поискового запроса."""
        if not self.has_permission('materials.view'):
            return
            
        try:
            txt = text.strip()
            if len(txt) < 2:
                self._load()
                return
            
            # Используем сервис для поиска с форматированием
            filtered = self.materials_service.search_materials_with_formatting(txt)
            self._load(filtered)
            
        except Exception as e:
            QMessageBox.warning(self, "Ошибка поиска", f"Ошибка поиска: {str(e)}")
            self._load()  # Возвращаемся к полному списку

    def _show_context_menu(self, pos: QPoint):
        """Показывает контекстное меню с проверкой прав."""
        if not self.has_permission('materials.view'):
            return
            
        row = self.tbl.rowAt(pos.y())
        if row < 0:
            return
            
        try:
            # Получаем материалы для определения ID
            materials = self.materials_service.get_all_materials()
            if row >= len(materials):
                return
                
            mat = materials[row]
            menu = QMenu(self)
            
            # Опции меню в зависимости от прав
            if self.has_permission('materials.delete'):
                text = 'Снять метку' if mat.get('to_delete') else 'Пометить на удаление'
                delete_action = menu.addAction(text)
            else:
                delete_action = None
            
            if self.has_permission('materials.edit'):
                edit_action = menu.addAction('Редактировать')
            else:
                edit_action = None
            
            if self.has_permission('documents.view'):
                docs_action = menu.addAction('Документы')
            else:
                docs_action = None
            
            # Показываем меню только если есть доступные действия
            if menu.actions():
                action = menu.exec_(self.tbl.viewport().mapToGlobal(pos))
                
                if action == delete_action and delete_action:
                    self._toggle_material_deletion(mat)
                elif action == edit_action and edit_action:
                    self._edit_material(mat)
                elif action == docs_action and docs_action:
                    self._show_material_documents(mat)
                    
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка в контекстном меню: {e}')

    @audit_action('create', 'material')
    def _add_material(self, checked=False):
        """Добавление нового материала с проверкой прав."""
        if not self.require_permission_gui('materials.create', 'добавления материала'):
            return
            
        try:
            dlg = AddMaterialDialog(self)
            dlg.setMinimumSize(800, 600)
            if dlg.exec_() == QDialog.Accepted:
                data = dlg.data()
                
                # Создаем материал через сервис
                material_id = self.materials_service.create(data)
                
                log_event(self.user, 'add_material', material_id, str(data))
                QMessageBox.information(self, 'Готово', f'Материал добавлен с ID: {material_id}')
                self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при добавлении материала: {e}')

    @audit_action('toggle_delete', 'material')
    def _toggle_material_deletion(self, material: Dict):
        """Переключение метки удаления материала."""
        try:
            material_id = material['id']
            user_login = self.user.get('login', 'unknown')
            
            if material['to_delete']:
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
            
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при изменении метки удаления: {e}')

    def _edit_material(self, material: Dict):
        """Редактирование материала."""
        QMessageBox.information(self, 'В разработке', 'Функция редактирования материала в разработке')

    def _show_material_documents(self, material: Dict):
        """Показ документов материала."""
        QMessageBox.information(self, 'В разработке', 'Функция просмотра документов в разработке')

    def _manual_refresh(self):
        """Ручное обновление данных."""
        if self.has_permission('materials.view'):
            try:
                # Очищаем кеш справочников
                self.materials_service.clear_cache()
                self._load()
                QMessageBox.information(self, "Обновление", "Данные обновлены")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка обновления: {str(e)}")

    def _on_poll(self):
        """Периодическая проверка изменений."""
        if not self.has_permission('materials.view'):
            return
            
        try:
            curr = len(self.materials_service.get_all_materials())
            if curr != self._last_count:
                # Можно подсветить кнопку Обновить
                pass
            self._last_count = curr
        except Exception as e:
            # Тихо игнорируем ошибки периодической проверки
            pass

    # Методы для открытия различных окон (с проверкой прав)
    
    def _open_settings(self):
        """Открытие настроек."""
        try:
            SettingsWindow(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии настроек: {e}')

    def _open_suppliers_admin(self):
        """Открытие справочника поставщиков."""
        if not self.require_permission_gui('suppliers.view', 'просмотра поставщиков'):
            return
        try:
            SuppliersAdmin(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии справочника поставщиков: {e}')

    def _open_grades_admin(self):
        """Открытие справочника марок."""
        if not self.require_permission_gui('admin.settings', 'управления справочниками'):
            return
        try:
            GradesAdmin(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии справочника марок: {e}')

    def _open_rolling_types_admin(self):
        """Открытие справочника видов проката."""
        if not self.require_permission_gui('admin.settings', 'управления справочниками'):
            return
        try:
            RollingTypesAdmin(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии справочника видов проката: {e}')

    def _open_moderation(self):
        """Открытие модерации удаления."""
        if not self.require_permission_gui('admin.users', 'модерации'):
            return
        try:
            ModerationDialog(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии модерации: {e}')

    def _open_audit(self):
        """Открытие журнала действий."""
        if not self.require_permission_gui('admin.logs', 'просмотра логов'):
            return
        try:
            AuditWindow(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии журнала действий: {e}')

    def _open_test_scenarios(self):
        """Открытие сценариев испытаний."""
        if not self.require_permission_gui('lab.edit', 'управления сценариями испытаний'):
            return
        try:
            TestScenariosAdmin(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии сценариев испытаний: {e}')

    def _open_otk(self):
        """Открытие модуля ОТК."""
        if not self.require_permission_gui('quality.view', 'работы с ОТК'):
            return
        try:
            OtkWindow(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии модуля ОТК: {e}')

    def _open_lab(self):
        """Открытие лаборатории."""
        if not self.require_permission_gui('lab.view', 'работы с лабораторией'):
            return
        try:
            LabWindow(self).show()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии лаборатории: {e}')

    def _open_defects(self):
        """Открытие журнала дефектов."""
        if not self.require_permission_gui('materials.view', 'просмотра дефектов'):
            return
        try:
            DefectsWindow(self).exec_()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при открытии журнала дефектов: {e}')

    def _change_password(self):
        """Смена пароля пользователя."""
        QMessageBox.information(self, 'В разработке', 'Функция смены пароля в разработке')

    def _show_my_permissions(self):
        """Показ прав текущего пользователя."""
        try:
            permissions = self.auth_service.get_user_permissions(self.current_user_id)
            roles = self.auth_service.get_user_roles(self.current_user_id)
            
            # Группируем права по категориям
            by_category = {}
            for perm in permissions:
                category = perm['category']
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(perm['display_name'])
            
            # Формируем текст для отображения
            info_text = f"Пользователь: {self.user['name']} ({self.user['login']})\n\n"
            
            info_text += "РОЛИ:\n"
            for role in roles:
                info_text += f"• {role['display_name']}\n"
            
            info_text += f"\nПРАВА ДОСТУПА ({len(permissions)}):\n"
            for category, perms in sorted(by_category.items()):
                info_text += f"\n{category.upper()}:\n"
                for perm in sorted(perms):
                    info_text += f"• {perm}\n"
            
            QMessageBox.information(self, 'Мои права доступа', info_text)
            
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при загрузке прав: {e}')

    def closeEvent(self, event):
        """Обработчик закрытия окна."""
        try:
            # Останавливаем все таймеры
            if hasattr(self, '_inactivity_timer'):
                self._inactivity_timer.stop()
            if hasattr(self, '_warning_timer'):
                self._warning_timer.stop()
            if hasattr(self, '_countdown_timer'):
                self._countdown_timer.stop()
            if hasattr(self, '_refresh_timer'):
                self._refresh_timer.stop()
            
            # Закрываем диалог предупреждения если он открыт
            if hasattr(self, '_warning_dialog') and self._warning_dialog:
                self._warning_dialog.close()
            
            # Выполняем logout через сервис авторизации с токеном сессии
            session_token = self.user.get('session_token')
            if session_token:
                self.auth_service.logout_user(self.current_user_id, session_token)
                log_event(self.user, 'app_close', 0, f'Пользователь {self.user["login"]} закрыл приложение')
            else:
                # Fallback для старого API
                self.auth_service.logout_user(self.current_user_id)
            
            # Закрытие соединения с БД
            self.db.close()
            
        except Exception as e:
            log_event(self.user, 'app_close_error', 0, f"Ошибка при закрытии приложения: {e}")
        
        super().closeEvent(event) 