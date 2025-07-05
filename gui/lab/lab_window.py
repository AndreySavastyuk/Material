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


class LabWindow(QMainWindow):
    STATUSES = ['Не отработана', 'В работе', 'ППСД пройден', 'Брак материала']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.user = parent.user
        self.db = Database(); self.db.connect()

        self.setWindowTitle('Модуль лаборатории (ЦЗЛ)')
        self.resize(900, 600)

        self._build_ui()
        self._load_requests()
        self._apply_filters()

    def _build_ui(self):
        mb = self.menuBar()
        file_menu = mb.addMenu('Файл')
        file_menu.addAction('Справочник образцов', lambda: SpecimenCatalogDialog(self).exec_())
        file_menu.addSeparator()
        file_menu.addAction('Закрыть', self.close)

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
        menu.addAction('Изменить статус',
                       lambda: self._change_status(rec))
        menu.addSeparator()
        menu.addAction('Редактировать сценарий',
                       lambda: self._guard_dialog(self._edit_scenario, rec))
        menu.addAction('Редактировать результаты',
                       lambda: self._guard_dialog(self._edit_results, rec))
        menu.addSeparator()
        menu.addAction('Экспорт в PDF',
                       lambda: self._guard_dialog(self._export_pdf, rec))
        menu.addAction('Отправить в Telegram',
                       lambda: self._guard_dialog(self._send_to_telegram, rec))
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

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)
