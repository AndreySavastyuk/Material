# gui/lab/lab_window.py

import os
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem, QAction, QMenu,
    QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QPushButton,
    QInputDialog, QStyle
)
from PyQt5.QtCore import Qt, QPoint
from db.database import Database
from gui.lab.pdf_generator import generate_pdf_for_request
from gui.lab.telegram_notifier import notify_request_passed, notify_material_defect
from gui.lab.request_editor import RequestEditor
from gui.lab.specimen_catalog import SpecimenCatalogDialog
from services.protocol_template_service import ProtocolTemplateService
from services.statistics_service import StatisticsService
from gui.lab.template_editor import TemplateManager
from gui.lab.template_preview import show_protocol_preview
from gui.lab.statistics_window import StatisticsWindow
from utils.logger import get_logger

logger = get_logger(__name__)


class LabWindow(QMainWindow):
    STATUSES = ['Не отработана', 'В работе', 'ППСД пройден', 'Брак материала']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.user = parent.user
        self.db = Database(); self.db.connect()
        
        # Инициализация сервисов
        self.template_service = ProtocolTemplateService(self.db.conn)
        self.statistics_service = StatisticsService(self.db.conn)

        self.setWindowTitle('Модуль лаборатории (ЦЗЛ)')
        self.resize(900, 600)

        self._build_ui()
        self._load_requests()
        self._apply_filters()

    def _build_ui(self):
        mb = self.menuBar()
        
        # Меню "Файл"
        file_menu = mb.addMenu('Файл')
        file_menu.addAction('Справочник образцов', lambda: SpecimenCatalogDialog(self).exec_())
        file_menu.addSeparator()
        file_menu.addAction('Закрыть', self.close)
        
        # Меню "Шаблоны"
        templates_menu = mb.addMenu('Шаблоны')
        templates_menu.addAction('Управление шаблонами', self._manage_templates)
        templates_menu.addSeparator()
        templates_menu.addAction('Создать шаблон', self._create_template)
        templates_menu.addAction('Импорт шаблонов', self._import_templates)
        templates_menu.addAction('Экспорт шаблонов', self._export_templates)
        
        # Меню "Отчеты"
        reports_menu = mb.addMenu('Отчеты')
        reports_menu.addAction('Генерация протокола', self._generate_protocol_from_selection)
        reports_menu.addAction('Массовая генерация', self._batch_generate_protocols)
        reports_menu.addSeparator()
        reports_menu.addAction('Статистика по шаблонам', self._show_template_statistics)
        
        # Меню "Анализ"
        analysis_menu = mb.addMenu('Анализ')
        analysis_menu.addAction('Статистический анализ', self._open_statistics_window)
        analysis_menu.addSeparator()
        analysis_menu.addAction('Анализ трендов', self._analyze_trends)
        analysis_menu.addAction('Сравнение партий', self._compare_batches)

        central = QWidget()
        self.setCentralWidget(central)
        vlay = QVBoxLayout(central)

        # Фильтры
        flay = QHBoxLayout()
        flay.addWidget(QLabel('Статус:'))
        self.combo_status = QComboBox()
        self.combo_status.addItems(['Все'] + self.STATUSES)
        flay.addWidget(self.combo_status)

        self.cb_arch = QCheckBox('Показать архивные')
        flay.addWidget(self.cb_arch)

        flay.addWidget(QLabel('Поиск:'))
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText('№ заявки или марка')
        flay.addWidget(self.le_search)

        flay.addStretch()
        vlay.addLayout(flay)

        # Таблица
        self.tbl = QTableWidget(0, 10)
        self.tbl.setHorizontalHeaderLabels([
            '№ заявки', 'Дата', 'Материал', 'Сценарий',
            'Испытания', 'Статус', 'Размер проката',
            'Плавка', 'Сертификат №', ''
        ])
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._show_context_menu)
        self.tbl.cellDoubleClicked.connect(self._on_cell_double_clicked)
        vlay.addWidget(self.tbl)

        # Сигналы
        self.combo_status.currentIndexChanged.connect(self._apply_filters)
        self.cb_arch.stateChanged.connect(self._apply_filters)
        self.le_search.textChanged.connect(self._apply_filters)

    def _load_requests(self):
        sql = """
            SELECT
                lr.id, lr.request_number, lr.creation_date,
                m.id AS material_id,
                g.grade AS material,
                lr.scenario_id, COALESCE(ts.name,'') AS scenario,
                lr.tests_json, lr.results_json,
                lr.status, lr.archived,
                rt.type AS rolling_type,
                m.size, m.heat_num, m.cert_num, m.cert_scan_path
            FROM lab_requests lr
            JOIN Materials m ON lr.material_id = m.id
            JOIN Grades g    ON m.grade_id    = g.id
            LEFT JOIN test_scenarios ts ON lr.scenario_id = ts.id
            LEFT JOIN RollingTypes   rt ON m.rolling_type_id = rt.id
            ORDER BY lr.id
        """
        cur = self.db.conn.cursor()
        cur.execute(sql)
        self.all_requests = []
        for r in cur.fetchall():
            tests = json.loads(r['tests_json'])
            results = json.loads(r['results_json'])
            self.all_requests.append({
                'id':             r['id'],
                'request_number': r['request_number'],
                'creation_date':  r['creation_date'],
                'material_id':    r['material_id'],
                'material':       r['material'],
                'scenario_id': r['scenario_id'],
                'scenario': r['scenario'],
                'tests': tests,
                'results': results,
                'tests_str': ', '.join(tests),
                'results_str': '; '.join(f"{x['name']}:{x.get('result', '')}" for x in results),
                'status':         r['status'],
                'archived':       r['archived'],
                'rolling_type':   r['rolling_type'],
                'size':           r['size'],
                'heat_num':       r['heat_num'],
                'cert_num':       r['cert_num'],
                'cert_scan_path': r['cert_scan_path']
            })

    def _apply_filters(self):
        st = self.combo_status.currentText()
        show_arch = self.cb_arch.isChecked()
        txt = self.le_search.text().lower()

        self.filtered = []
        for r in self.all_requests:
            if not show_arch and r['archived']:
                continue
            if st != 'Все' and r['status'] != st:
                continue
            if txt and txt not in r['request_number'].lower() and txt not in r['material'].lower():
                continue
            self.filtered.append(r)
        self._populate_table()

    def _populate_table(self):
        self.tbl.setRowCount(len(self.filtered))
        for i, r in enumerate(self.filtered):
            vals = [
                r['request_number'], r['creation_date'], r['material'], r['scenario'],
                r['tests_str'],        r['status'],
                f"{r['rolling_type']} {r['size']}",
                r['heat_num'] or '',   r['cert_num'] or ''
            ]
            for j, v in enumerate(vals):
                itm = QTableWidgetItem(str(v))
                itm.setTextAlignment(Qt.AlignCenter)
                if j == 5:
                    color = Qt.lightGray if v == 'Не отработана' else \
                            Qt.yellow    if v == 'В работе'      else \
                            Qt.green     if v == 'ППСД пройден'  else \
                            Qt.red
                    itm.setBackground(color)
                self.tbl.setItem(i, j, itm)

            icon_item = QTableWidgetItem()
            if r['cert_scan_path']:
                icon = self.style().standardIcon(QStyle.SP_DialogOpenButton)
                icon_item.setIcon(icon)
            icon_item.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(i, 9, icon_item)

        self.tbl.resizeColumnsToContents()

    def _on_cell_double_clicked(self, row: int, col: int):
        rec = self.filtered[row]
        if col == 9:  # столбец сертификата
            path = rec.get('cert_scan_path') or ''
            if path and os.path.exists(path):
                os.startfile(path)
            else:
                QMessageBox.warning(self, 'Ошибка', 'Сертификат не найден')
            return

        from gui.lab.request_editor import RequestEditor  # импорт модуля
        dlg = RequestEditor(self, rec['id'])  # передаем ID заявки
        dlg.exec_()

        # после закрытия окна — перезагружаем таблицу
        self._load_requests()
        self._apply_filters()

    def _show_context_menu(self, pos: QPoint):
        row = self.tbl.rowAt(pos.y())
        if row < 0:
            return
        rec = self.filtered[row]
        menu = QMenu(self)
        
        menu.addAction('Изменить статус', lambda: self._change_status(rec))
        menu.addSeparator()
        menu.addAction('Редактировать сценарий', lambda: self._guard_dialog(self._edit_scenario, rec))
        menu.addAction('Редактировать результаты', lambda: self._guard_dialog(self._edit_results, rec))
        menu.addSeparator()
        
        # Новые пункты меню для шаблонов
        templates_submenu = menu.addMenu('Протоколы')
        templates_submenu.addAction('Генерировать по шаблону', lambda: self._generate_protocol_for_request(rec))
        templates_submenu.addAction('Предварительный просмотр', lambda: self._preview_protocol_for_request(rec))
        templates_submenu.addSeparator()
        templates_submenu.addAction('Экспорт в PDF (старый)', lambda: self._guard_dialog(self._export_pdf, rec))
        
        # Подменю для статистического анализа
        analysis_submenu = menu.addMenu('Анализ')
        analysis_submenu.addAction('Статистический анализ', self._open_statistics_window)
        analysis_submenu.addAction('Анализ по материалу', lambda: self._analyze_material_statistics(rec))
        
        menu.addSeparator()
        menu.addAction('Отправить в Telegram', lambda: self._guard_dialog(self._send_to_telegram, rec))
        
        menu.exec_(self.tbl.viewport().mapToGlobal(pos))

    def _change_status(self, rec: dict):
        """Диалог выбора нового статуса и автоматическое уведомление."""
        cur_status = rec['status']
        items = self.STATUSES
        idx, ok = QInputDialog.getItem(
            self, 'Изменить статус', 'Новый статус:', items, items.index(cur_status), False
        )
        if not ok or idx == cur_status:
            return

        # Обновляем статус в БД
        self.db.conn.execute(
            'UPDATE lab_requests SET status=? WHERE id=?',
            (idx, rec['id'])
        )
        self.db.conn.commit()

        # Уведомляем в Telegram
        if idx == 'ППСД пройден':
            notify_request_passed(rec)
        elif idx == 'Брак материала':
            notify_material_defect(rec)

        # Обновляем локальный rec и таблицу
        rec['status'] = idx
        self._apply_filters()

        QMessageBox.information(self, 'Telegram', f'Уведомление отправлено: {idx}')

    def _guard_dialog(self, func, rec: dict):
        mat_id = rec['material_id']
        locked, locker = self.db.is_locked(mat_id)
        if locked and locker != self.user['login']:
            QMessageBox.warning(self, 'Заблокировано',
                                f'Запись редактирует {locker}.')
            return
        if not self.db.acquire_lock(mat_id, self.user['login']):
            QMessageBox.warning(self, 'Ошибка', 'Не удалось взять блокировку.')
            return
        try:
            func(rec)
        finally:
            self.db.release_lock(mat_id, self.user['login'])
            self._load_requests()
            self._apply_filters()

    def _edit_scenario(self, rec: dict):
        """Диалог редактирования сценария заявки."""
        dlg = QDialog(self)
        dlg.setWindowTitle('Редактирование сценария')
        form = QFormLayout(dlg)

        # Заберём все доступные сценарии из БД
        cur = self.db.conn.cursor()
        cur.execute("SELECT id, name, tests_json FROM test_scenarios")
        scenarios = cur.fetchall()

        combo = QComboBox()
        # наполняем выпадашку
        for s in scenarios:
            combo.addItem(s['name'], s['id'])
        # выбираем текущий
        idx = combo.findData(rec['scenario_id'])
        if idx >= 0:
            combo.setCurrentIndex(idx)
        form.addRow('Сценарий:', combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)

        if dlg.exec_() == QDialog.Accepted:
            new_id = combo.currentData()
            # найдём JSON тестов для выбранного сценария
            tests_json = next(s['tests_json'] for s in scenarios if s['id'] == new_id)
            self.db.conn.execute(
                'UPDATE lab_requests SET scenario_id=?, tests_json=? WHERE id=?',
                (new_id, tests_json, rec['id'])
            )
            self.db.conn.commit()

    def _edit_results(self, rec: dict):
        """Диалог редактирования результатов испытаний."""
        dlg = QDialog(self)
        dlg.setWindowTitle('Редактирование результатов')
        form = QFormLayout(dlg)

        # создаём поле для каждого теста
        inputs = {}
        for test in rec['tests']:
            le = QLineEdit()
            # подставляем существующее значение, если есть
            existing = next((r['result'] for r in rec['results'] if r['name'] == test), '')
            le.setText(str(existing))
            form.addRow(f"{test}:", le)
            inputs[test] = le

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)

        if dlg.exec_() == QDialog.Accepted:
            # собираем новую структуру results_json
            new_results = [
                {'name': test, 'result': inputs[test].text().strip()}
                for test in rec['tests']
            ]
            new_json = json.dumps(new_results, ensure_ascii=False)
            self.db.conn.execute(
                'UPDATE lab_requests SET results_json=? WHERE id=?',
                (new_json, rec['id'])
            )
            self.db.conn.commit()

    def _export_pdf(self, rec: dict):
        """Экспорт заявки в PDF по текущим данным."""
        try:
            generate_pdf_for_request(rec)
            QMessageBox.information(self, 'PDF', 'Экспорт в PDF выполнен.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка PDF', str(e))

    def _send_to_telegram(self, rec: dict):
        """Отправка уведомления в Telegram в зависимости от статуса."""
        try:
            if rec['status'] == 'ППСД пройден':
                notify_request_passed(rec)
            else:
                notify_material_defect(rec)
            QMessageBox.information(self, 'Telegram', 'Уведомление отправлено.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка Telegram', str(e))

    # Методы для работы с шаблонами
    def _manage_templates(self):
        """Открытие менеджера шаблонов."""
        try:
            dialog = TemplateManager(self.template_service, self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Ошибка открытия менеджера шаблонов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть менеджер шаблонов: {e}")

    def _create_template(self):
        """Создание нового шаблона."""
        try:
            from gui.lab.template_editor import TemplateEditor
            dialog = TemplateEditor(self.template_service, parent=self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Ошибка создания шаблона: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать шаблон: {e}")

    def _generate_protocol_from_selection(self):
        """Генерация протокола для выбранной заявки."""
        current_row = self.tbl.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите заявку для генерации протокола")
            return
        
        rec = self.filtered[current_row]
        self._generate_protocol_for_request(rec)

    def _generate_protocol_for_request(self, rec: dict):
        """Генерация протокола для конкретной заявки."""
        try:
            show_protocol_preview(self.template_service, rec, self)
        except Exception as e:
            logger.error(f"Ошибка генерации протокола: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сгенерировать протокол: {e}")

    def _preview_protocol_for_request(self, rec: dict):
        """Предварительный просмотр протокола для заявки."""
        try:
            show_protocol_preview(self.template_service, rec, self)
        except Exception as e:
            logger.error(f"Ошибка предварительного просмотра: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось показать предварительный просмотр: {e}")

    def _batch_generate_protocols(self):
        """Массовая генерация протоколов."""
        try:
            # Получаем все заявки с определенным статусом
            completed_requests = [r for r in self.filtered if r['status'] == 'ППСД пройден']
            
            if not completed_requests:
                QMessageBox.information(self, "Информация", "Нет заявок со статусом 'ППСД пройден'")
                return
            
            reply = QMessageBox.question(
                self, "Массовая генерация", 
                f"Сгенерировать протоколы для {len(completed_requests)} заявок?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь можно добавить диалог выбора шаблона и параметров
                QMessageBox.information(self, "В разработке", "Функция массовой генерации в разработке")
                
        except Exception as e:
            logger.error(f"Ошибка массовой генерации: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить массовую генерацию: {e}")

    def _import_templates(self):
        """Импорт шаблонов из файла."""
        try:
            from PyQt5.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Выбор файла шаблонов", "", "JSON files (*.json)"
            )
            
            if file_path:
                # Здесь можно добавить логику импорта
                QMessageBox.information(self, "В разработке", "Функция импорта шаблонов в разработке")
                
        except Exception as e:
            logger.error(f"Ошибка импорта шаблонов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать шаблоны: {e}")

    def _export_templates(self):
        """Экспорт шаблонов в файл."""
        try:
            from PyQt5.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранение шаблонов", "templates.json", "JSON files (*.json)"
            )
            
            if file_path:
                # Здесь можно добавить логику экспорта
                QMessageBox.information(self, "В разработке", "Функция экспорта шаблонов в разработке")
                
        except Exception as e:
            logger.error(f"Ошибка экспорта шаблонов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать шаблоны: {e}")

    def _show_template_statistics(self):
        """Показ статистики по использованию шаблонов."""
        try:
            templates = self.template_service.get_all_templates()
            
            stats_text = "Статистика по шаблонам:\n\n"
            for template in templates:
                stats_text += f"• {template['name']}\n"
                stats_text += f"  Категория: {template['category']}\n"
                stats_text += f"  Версия: {template['version']}\n"
                stats_text += f"  Активный: {'Да' if template['is_active'] else 'Нет'}\n\n"
            
            QMessageBox.information(self, "Статистика шаблонов", stats_text)
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить статистику: {e}")

    # Методы для статистического анализа
    def _open_statistics_window(self):
        """Открытие окна статистического анализа."""
        try:
            dialog = StatisticsWindow(self.statistics_service, self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Ошибка открытия окна статистики: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть окно статистического анализа: {e}")

    def _analyze_material_statistics(self, rec: dict):
        """Анализ статистики по конкретному материалу."""
        try:
            # Открываем окно статистики с предустановленным материалом
            dialog = StatisticsWindow(self.statistics_service, self)
            
            # Предварительно устанавливаем материал
            material_grade = rec.get('material', '')
            if material_grade:
                # Ищем материал в комбобоксе и устанавливаем его
                for i in range(dialog.material_combo.count()):
                    if dialog.material_combo.itemText(i) == material_grade:
                        dialog.material_combo.setCurrentIndex(i)
                        break
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Ошибка анализа статистики материала: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить анализ: {e}")

    def _analyze_trends(self):
        """Анализ трендов в результатах испытаний."""
        try:
            # Получаем список доступных тестов
            tests = self.statistics_service.get_available_tests()
            
            if not tests:
                QMessageBox.information(self, "Информация", "Нет доступных тестов для анализа трендов")
                return
            
            # Диалог выбора теста для анализа тренда
            test_name, ok = QInputDialog.getItem(
                self, "Анализ трендов", "Выберите тест для анализа:", tests, 0, False
            )
            
            if ok and test_name:
                # Получаем данные за последние 90 дней
                data = self.statistics_service.get_test_results_data(test_name, None, 90)
                
                if not data:
                    QMessageBox.information(self, "Информация", f"Нет данных для теста '{test_name}'")
                    return
                
                # Простой анализ тренда
                values = [item['value'] for item in data]
                
                if len(values) < 3:
                    QMessageBox.information(self, "Информация", "Недостаточно данных для анализа тренда")
                    return
                
                # Расчет коэффициента корреляции с временем
                import numpy as np
                from scipy import stats as scipy_stats
                
                x = np.arange(len(values))
                slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, values)
                
                trend_info = f"""Анализ тренда для теста '{test_name}':

Количество точек: {len(values)}
Период: {data[0]['date']} - {data[-1]['date']}

Коэффициент наклона: {slope:.6f}
Коэффициент корреляции (R): {r_value:.4f}
R² (детерминация): {r_value**2:.4f}
P-значение: {p_value:.6f}
Стандартная ошибка: {std_err:.6f}

Интерпретация:
"""
                
                if abs(r_value) > 0.7 and p_value < 0.05:
                    if slope > 0:
                        trend_info += "• Обнаружен статистически значимый возрастающий тренд"
                    else:
                        trend_info += "• Обнаружен статистически значимый убывающий тренд"
                elif abs(r_value) > 0.3:
                    trend_info += "• Присутствует слабый тренд, требуется дополнительное наблюдение"
                else:
                    trend_info += "• Тренд отсутствует, процесс стабилен"
                
                QMessageBox.information(self, "Результаты анализа тренда", trend_info)
                
        except Exception as e:
            logger.error(f"Ошибка анализа трендов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить анализ трендов: {e}")

    def _compare_batches(self):
        """Сравнение разных партий материала."""
        try:
            # Получаем список марок материалов
            grades = self.statistics_service.get_material_grades()
            
            if len(grades) < 2:
                QMessageBox.information(self, "Информация", "Недостаточно марок материалов для сравнения")
                return
            
            # Диалог выбора марок для сравнения
            grade1, ok1 = QInputDialog.getItem(
                self, "Сравнение партий", "Выберите первую марку:", grades, 0, False
            )
            
            if not ok1:
                return
            
            remaining_grades = [g for g in grades if g != grade1]
            grade2, ok2 = QInputDialog.getItem(
                self, "Сравнение партий", "Выберите вторую марку:", remaining_grades, 0, False
            )
            
            if not ok2:
                return
            
            # Выбор теста для сравнения
            tests = self.statistics_service.get_available_tests()
            test_name, ok3 = QInputDialog.getItem(
                self, "Сравнение партий", "Выберите тест для сравнения:", tests, 0, False
            )
            
            if not ok3:
                return
            
            # Получаем данные для обеих марок
            data1 = self.statistics_service.get_test_results_data(test_name, grade1, 90)
            data2 = self.statistics_service.get_test_results_data(test_name, grade2, 90)
            
            if not data1 or not data2:
                QMessageBox.information(self, "Информация", "Недостаточно данных для сравнения")
                return
            
            values1 = [item['value'] for item in data1]
            values2 = [item['value'] for item in data2]
            
            # Расчет статистик
            stats1 = self.statistics_service.calculate_basic_statistics(values1)
            stats2 = self.statistics_service.calculate_basic_statistics(values2)
            
            # t-тест для сравнения средних
            from scipy import stats as scipy_stats
            t_stat, p_value = scipy_stats.ttest_ind(values1, values2)
            
            comparison_info = f"""Сравнение партий материалов:

{grade1} (n={len(values1)}):
• Среднее: {stats1.get('mean', 0):.3f}
• СКО: {stats1.get('std', 0):.3f}
• Медиана: {stats1.get('median', 0):.3f}

{grade2} (n={len(values2)}):
• Среднее: {stats2.get('mean', 0):.3f}
• СКО: {stats2.get('std', 0):.3f}
• Медиана: {stats2.get('median', 0):.3f}

t-тест для сравнения средних:
• t-статистика: {t_stat:.4f}
• p-значение: {p_value:.6f}

Вывод:
"""
            
            if p_value < 0.05:
                comparison_info += "• Различия между партиями статистически значимы (p < 0.05)"
            else:
                comparison_info += "• Различия между партиями не значимы (p ≥ 0.05)"
            
            QMessageBox.information(self, "Результаты сравнения партий", comparison_info)
            
        except Exception as e:
            logger.error(f"Ошибка сравнения партий: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить сравнение партий: {e}")

    def closeEvent(self, event):
        try:
            self.db.close()
        except:
            pass
        super().closeEvent(event)
