# gui/lab/request_editor.py

import os
import json
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QComboBox, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QDialogButtonBox, QGroupBox, QScrollArea, QDoubleSpinBox,
    QSpinBox, QStyle
)
from PyQt5.QtCore import Qt
from db.database import Database
from gui.lab.pdf_generator import generate_pdf_for_request


class RequestEditor(QDialog):
    """Единое окно редактирования заявки лаборатории."""
    def __init__(self, parent, request_id: int):
        super().__init__(parent)
        self.db   = Database(); self.db.connect()
        self.user = parent.user
        self.req  = self._load_request(request_id)

        # Загружаем справочник сценариев
        cur = self.db.conn.execute("SELECT id,name,tests_json FROM test_scenarios")
        self._scenarios = cur.fetchall()

        self.setWindowTitle(f"Заявка {self.req['request_number']}")
        self.resize(820, 600)

        self._build_ui()

    def _load_request(self, rid: int) -> dict:
        row = self.db.conn.execute(
            """SELECT lr.*, g.grade, rt.type AS rolling_type,
                      m.size, m.heat_num, m.cert_num, m.cert_scan_path
               FROM lab_requests lr
               JOIN Materials m ON lr.material_id = m.id
               JOIN Grades    g ON m.grade_id    = g.id
               LEFT JOIN RollingTypes rt ON m.rolling_type_id = rt.id
               WHERE lr.id=?""", (rid,)
        ).fetchone()
        rec = dict(row)
        rec["tests"]   = json.loads(rec["tests_json"])
        rec["results"] = json.loads(rec["results_json"])
        return rec

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # — Вкладка «Сценарий» —
        tab_scn = QWidget()
        v_scn = QVBoxLayout(tab_scn)
        form_scn = QFormLayout()
        self.cmb_scn = QComboBox()
        for s in self._scenarios:
            self.cmb_scn.addItem(s["name"], s["id"])
        idx = self.cmb_scn.findData(self.req["scenario_id"])
        if idx >= 0:
            self.cmb_scn.setCurrentIndex(idx)
        form_scn.addRow("Сценарий:", self.cmb_scn)
        v_scn.addLayout(form_scn)
        btn_scn = QPushButton("Сохранить сценарий")
        btn_scn.clicked.connect(self._save_scenario)
        v_scn.addWidget(btn_scn)
        self.tabs.addTab(tab_scn, "Сценарий")

        # — Вкладка «Испытания» —
        self._build_tests_tab()

        # — Вкладка «Комментарии» —
        tab_com = QWidget()
        v_com = QVBoxLayout(tab_com)
        self.list_comments = QListWidget(); v_com.addWidget(self.list_comments)
        self._load_comments()
        self.te_comment = QTextEdit(); self.te_comment.setFixedHeight(60); v_com.addWidget(self.te_comment)
        btn_add = QPushButton("Добавить комментарий"); btn_add.clicked.connect(self._add_comment); v_com.addWidget(btn_add)
        self.tabs.addTab(tab_com, "Комментарии")

        # — Вкладка «История» —
        tab_log = QWidget()
        v_log = QVBoxLayout(tab_log)
        self.list_logs = QListWidget(); v_log.addWidget(self.list_logs)
        self._load_logs()
        self.tabs.addTab(tab_log, "История")

        # — Нижняя панель: PDF и сертификат —
        h = QHBoxLayout()
        btn_pdf = QPushButton("Создать PDF‑бланк"); btn_pdf.clicked.connect(self._export_pdf)
        h.addWidget(btn_pdf)
        if self.req["cert_scan_path"]:
            btn_open = QPushButton("Сертификат")
            btn_open.clicked.connect(lambda: os.startfile(self.req["cert_scan_path"]))
            h.addWidget(btn_open)
        h.addStretch()
        h.addWidget(QDialogButtonBox(QDialogButtonBox.Close, parent=self, accepted=self.accept))
        layout.addLayout(h)

    def _build_tests_tab(self):
        # Если вкладка уже есть – удаляем её
        try:
            i = self.tabs.indexOf(self.tab_tests)
            if i >= 0:
                self.tabs.removeTab(i)
        except AttributeError:
            pass

        self.tab_tests = QWidget()
        v_tests = QVBoxLayout(self.tab_tests)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        container = QWidget(); v = QVBoxLayout(container)
        scroll.setWidget(container)

        self.test_widgets = {}
        for test in self.req["tests"]:
            grp = QGroupBox(test)
            grp.setCheckable(True)
            grp.setChecked(True)
            form = QFormLayout(grp)
            widgets = {}

            # динамика полей по типу испытания
            if test == "Растяжение":
                # выпадающий список образцов
                cur = self.db.conn.execute("SELECT id, name FROM Specimens")
                combo = QComboBox()
                for s in cur.fetchall():
                    combo.addItem(s["name"], s["id"])
                # spinbox для количества
                cnt = QSpinBox();
                cnt.setRange(1, 100)
                form.addRow("Образец:", combo)
                form.addRow("Кол-во образцов:", cnt)
                widgets = {"specimen": combo, "count": cnt}
                sb1 = QDoubleSpinBox(); sb1.setSuffix(" MPa"); sb1.setRange(0,2000)
                sb2 = QDoubleSpinBox(); sb2.setSuffix(" MPa"); sb2.setRange(0,2000)
                sb3 = QDoubleSpinBox(); sb3.setSuffix(" %");   sb3.setRange(0,100)
                form.addRow("σ₀.₂:", sb1); form.addRow("σᵥ:", sb2); form.addRow("δ:", sb3)
                widgets = {"σ₀.₂":sb1, "σᵥ":sb2, "δ":sb3}

            elif test == "Ударный изгиб":
                cur = self.db.conn.execute("SELECT id, name FROM Specimens")
                combo = QComboBox()
                for s in cur.fetchall():
                    combo.addItem(s["name"], s["id"])
                cnt = QSpinBox();
                cnt.setRange(1, 100)
                form.addRow("Образец:", combo)
                form.addRow("Кол-во образцов:", cnt)
                widgets = {"specimen": combo, "count": cnt}
                sb20  = QDoubleSpinBox(); sb20.setSuffix(" J"); sb20.setRange(0,500)
                sb350 = QDoubleSpinBox(); sb350.setSuffix(" J"); sb350.setRange(0,500)
                form.addRow("E @20°C:", sb20); form.addRow("E @350°C:", sb350)
                widgets = {"E20":sb20, "E350":sb350}

            elif test == "Твёрдость":
                hb = QSpinBox(); hb.setSuffix(" HB"); hb.setRange(0,1000)
                form.addRow("HB:", hb)
                widgets = {"HB":hb}

            elif test in ("МКК","Контроль макроструктуры"):
                combo = QComboBox(); combo.addItems(["Соответствует","Не соответствует"])
                form.addRow("Результат:", combo)
                widgets = {"pass":combo}

            else:
                le = QLineEdit()
                form.addRow("Значение:", le)
                widgets = {"val":le}

            # предзаполняем существующими результатами
            for r in self.req["results"]:
                if r["name"] == test:
                    if isinstance(r["result"], dict):
                        for k,w in widgets.items():
                            if k in r["result"]:
                                if hasattr(w,"setValue"):
                                    w.setValue(float(r["result"][k]))
                                else:
                                    w.setText(str(r["result"][k]))
                    else:
                        w = next(iter(widgets.values()))
                        if hasattr(w,"setValue"):
                            w.setValue(float(r["result"]))
                        else:
                            w.setText(str(r["result"]))

            grp.setLayout(form)
            v.addWidget(grp)
            self.test_widgets[test] = (grp, widgets)

        v.addStretch()
        v_tests.addWidget(scroll)
        btn_res = QPushButton("Сохранить результаты"); btn_res.clicked.connect(self._save_results)
        v_tests.addWidget(btn_res)
        self.tabs.addTab(self.tab_tests, "Испытания")

    def _save_scenario(self):
        new_id = self.cmb_scn.currentData()
        tests_json = next(s["tests_json"] for s in self._scenarios if s["id"]==new_id)
        self.db.conn.execute(
            "UPDATE lab_requests SET scenario_id=?, tests_json=? WHERE id=?",
            (new_id, tests_json, self.req["id"])
        )
        self.db.conn.execute(
            "UPDATE test_scenarios SET tests_json=? WHERE id=?",
            (tests_json, new_id)
        )
        payload = json.dumps({
            "old_scenario": self.req["scenario_id"],
            "new_scenario": new_id
        }, ensure_ascii=False)
        self.db.conn.execute(
            "INSERT INTO lab_logs(request_id,author,action,payload) VALUES(?,?,?,?)",
            (self.req["id"], self.user["login"], "edit_scenario", payload)
        )
        self.db.conn.commit()
        self.req["scenario_id"] = new_id
        self.req["tests"] = json.loads(tests_json)
        self._build_tests_tab()
        QMessageBox.information(self, "Сохранено", "Сценарий обновлён")

    def _save_results(self):
        new_results = []
        for name,(grp,widgets) in self.test_widgets.items():
            if not grp.isChecked(): continue
            entry = {"name": name}
            if "specimen" in widgets:
                entry["specimen_id"] = widgets["specimen"].currentData()
                entry["quantity"] = widgets["count"].value()
            vals={}
            for k,w in widgets.items():
                val = w.value() if hasattr(w,"value") else w.text().strip()
                vals[k]=val
            res = vals["val"] if list(vals.keys())==["val"] else vals
            new_results.append({"name":name,"result":res})
        json_txt = json.dumps(new_results, ensure_ascii=False)
        self.db.conn.execute(
            "UPDATE lab_requests SET results_json=? WHERE id=?",
            (json_txt, self.req["id"])
        )
        self.db.conn.execute(
            "INSERT INTO lab_logs(request_id,author,action,payload) VALUES(?,?,?,?)",
            (self.req["id"], self.user["login"], "edit_results", json_txt)
        )
        self.db.conn.commit()
        QMessageBox.information(self, "Сохранено", "Результаты сохранены")
        new_results.append(entry)

    def _load_comments(self):
        self.list_comments.clear()
        cur = self.db.conn.execute(
            "SELECT author,body,created_at FROM lab_comments WHERE request_id=? ORDER BY id",
            (self.req["id"],)
        )
        for c in cur.fetchall():
            txt = f"[{c['created_at']}] {c['author']}: {c['body']}"
            QListWidgetItem(txt, self.list_comments)

    def _add_comment(self):
        body=self.te_comment.toPlainText().strip()
        if not body: return
        self.db.conn.execute(
            "INSERT INTO lab_comments(request_id,author,body) VALUES(?,?,?)",
            (self.req["id"], self.user["login"], body)
        )
        self.db.conn.execute(
            "INSERT INTO lab_logs(request_id,author,action,payload) VALUES(?,?,?,?)",
            (self.req["id"], self.user["login"], "add_comment", body)
        )
        self.db.conn.commit()
        self.te_comment.clear()
        self._load_comments()

    def _load_logs(self):
        self.list_logs.clear()
        cur = self.db.conn.execute(
            "SELECT at,author,action FROM lab_logs WHERE request_id=? ORDER BY id",
            (self.req["id"],)
        )
        for l in cur.fetchall():
            txt = f"{l['at']} — {l['author']} — {l['action']}"
            QListWidgetItem(txt, self.list_logs)

    def _export_pdf(self):
        try:
            generate_pdf_for_request(self.req)
            QMessageBox.information(self, "PDF", "Бланк сформирован")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка PDF", str(e))

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)
