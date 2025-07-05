# db/database.py

import sqlite3
import os
import datetime
from config import load_config

class Database:
    def __init__(self, db_path=None):
        cfg = load_config()
        # Секция DATABASE:path
        db_cfg = cfg.get('DATABASE', {})
        default_db = os.path.join(os.getcwd(), 'materials.db')
        self.db_path = db_path or db_cfg.get('path', default_db)
        # Секция DOCUMENTS:root_path
        doc_cfg = cfg.get('DOCUMENTS', {})
        self.docs_root = doc_cfg.get('root_path', os.path.join(os.getcwd(), 'docs'))
        self.conn = None

    def connect(self):
        """
        Подключаемся к SQLite, включаем внешние ключи и инициализируем схему.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.initialize_schema()
        return self.conn

    def initialize_schema(self):
        """
        Создаёт или дополняет таблицы:
        Suppliers, Grades, RollingTypes, Materials, Documents,
        Users, lab_requests, test_scenarios и добавляет недостающие колонки:
        to_delete в Materials, results_json и last_pdf_path в lab_requests,
        а также поля для Materials по ТЗ.
        """
        cursor = self.conn.cursor()

        # Базовое создание таблиц
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS Suppliers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Grades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade TEXT UNIQUE NOT NULL,
            density REAL NOT NULL,
            standard TEXT
        );
        CREATE TABLE IF NOT EXISTS RollingTypes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT UNIQUE NOT NULL,
            icon_path TEXT
        );
        CREATE TABLE IF NOT EXISTS Materials(
            id INTEGER PRIMARY KEY AUTOINCREMENT
        );
        CREATE TABLE IF NOT EXISTS Documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL REFERENCES Materials(id),
            doc_type TEXT,
            file_path TEXT,
            upload_date TEXT,
            uploaded_by TEXT
        );
        CREATE TABLE IF NOT EXISTS lab_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creation_date TEXT NOT NULL,
            request_number TEXT NOT NULL,
            material_id INTEGER NOT NULL REFERENCES Materials(id),
            tests_json TEXT NOT NULL,
            results_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS test_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL REFERENCES Grades(id),
            name TEXT NOT NULL,
            tests_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT,
            salt TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS RecordLocks(
        material_id  INTEGER PRIMARY KEY REFERENCES Materials(id),
        locked_by    TEXT    NOT NULL,
        locked_at    TEXT    NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS defects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id INTEGER NOT NULL REFERENCES Materials(id),
        defect_type    TEXT    NOT NULL,
        description    TEXT,
        reported_by    TEXT,
        timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP,
        to_delete      INTEGER DEFAULT 0
        );

        -- Индексы для быстрого поиска
        CREATE INDEX IF NOT EXISTS idx_defects_material ON defects(material_id);
        CREATE INDEX IF NOT EXISTS idx_defects_type     ON defects(defect_type);
        CREATE INDEX IF NOT EXISTS idx_defects_time     ON defects(timestamp);

        CREATE TABLE IF NOT EXISTS lab_comments (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id    INTEGER NOT NULL REFERENCES lab_requests(id),
          author        TEXT    NOT NULL,
          body          TEXT    NOT NULL,
          created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
          to_delete     INTEGER NOT NULL DEFAULT 0
        );
        
        CREATE INDEX IF NOT EXISTS idx_lab_comments_req ON lab_comments(request_id);
        
        -- 2) журнал изменений
        CREATE TABLE IF NOT EXISTS lab_logs (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id  INTEGER NOT NULL REFERENCES lab_requests(id),
          author      TEXT    NOT NULL,
          action      TEXT    NOT NULL,      -- "edit_results", "change_status", …
          payload     TEXT,                  -- JSON с детальными изменениями
          at          TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS Specimens (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          name        TEXT    NOT NULL UNIQUE,
          pdf_path    TEXT    NOT NULL,
          created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX IF NOT EXISTS idx_lab_logs_req ON lab_logs(request_id);
        ''')

        existing = {row['name'] for row in self.conn.execute("PRAGMA table_info(Specimens)")}
        extras = {
            'test_type': "TEXT DEFAULT ''",  # 'Растяжение' или 'Ударный изгиб'
            'length_mm': "REAL DEFAULT 0",  # длина заготовки в мм
            'standard': "TEXT DEFAULT ''",  # номер ГОСТ
            'sample_number': "TEXT DEFAULT ''",  # номер образца
            'specimen_type': "TEXT DEFAULT ''"  # тип образца (штанга, брусок и т.п.)
        }
        for col, definition in extras.items():
            if col not in existing:
                self.conn.execute(f"ALTER TABLE Specimens ADD COLUMN {col} {definition}")
        self.conn.commit()

        cur = self.conn.execute("PRAGMA table_info(Materials)")
        cols = [row["name"] for row in cur.fetchall()]
        if "cert_saved_at" not in cols:
            self.conn.execute("ALTER TABLE Materials ADD COLUMN cert_saved_at TEXT")
            self.conn.commit()

        if "cert_scan_path" not in cols:
            self.conn.execute("ALTER TABLE Materials ADD COLUMN cert_scan_path TEXT")
            self.conn.commit()

        # Soft-delete: добавляем поле to_delete в Materials
        existing_mat = {col['name'] for col in cursor.execute("PRAGMA table_info(Materials)")}
        if 'to_delete' not in existing_mat:
            self.conn.execute("ALTER TABLE Materials ADD COLUMN to_delete INTEGER NOT NULL DEFAULT 0")

        # Добавление тестового администратора, если нет
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Users WHERE login='admin'")
        if cur.fetchone()[0] == 0:
            import hashlib
            pwd = hashlib.sha256('admin'.encode('utf-8')).hexdigest()
            cur.execute(
                "INSERT INTO Users(login, password_hash, role, name, salt) VALUES(?,?,?,?,?)",
                ('admin', pwd, 'Администратор', 'Админ', '')
            )

        # Убедимся, что в lab_requests есть колонки results_json и last_pdf_path
        existing_req = {col['name'] for col in cursor.execute("PRAGMA table_info(lab_requests)")}
        if 'results_json' not in existing_req:
            self.conn.execute(
                "ALTER TABLE lab_requests ADD COLUMN results_json TEXT NOT NULL DEFAULT '[]'"
            )
        if 'last_pdf_path' not in existing_req:
            self.conn.execute(
                "ALTER TABLE lab_requests ADD COLUMN last_pdf_path TEXT DEFAULT ''"
            )

        # Добавление недостающих колонок в Materials по ТЗ
        existing = {col['name'] for col in cursor.execute("PRAGMA table_info(Materials)")}
        required = {
            'arrival_date':         "TEXT DEFAULT ''",
            'supplier_id':          "INTEGER DEFAULT NULL",
            'order_num':            "TEXT DEFAULT ''",
            'grade_id':             "INTEGER DEFAULT NULL",
            'rolling_type_id':      "INTEGER DEFAULT NULL",
            'size':                 "TEXT DEFAULT ''",
            'cert_num':             "TEXT DEFAULT ''",
            'cert_date':            "TEXT DEFAULT ''",
            'batch':                "TEXT DEFAULT ''",
            'heat_num':             "TEXT DEFAULT ''",
            'volume_length_mm':     "REAL DEFAULT 0",
            'volume_weight_kg':     "REAL DEFAULT 0",
            'otk_remarks':          "TEXT DEFAULT ''",
            'needs_lab':            "INTEGER DEFAULT 0"
        }
        for col, definition in required.items():
            if col not in existing:
                self.conn.execute(f"ALTER TABLE Materials ADD COLUMN {col} {definition}")

        if 'scenario_id' not in existing_req:
            self.conn.execute(
                "ALTER TABLE lab_requests ADD COLUMN scenario_id INTEGER REFERENCES test_scenarios(id)"
            )
        self.conn.executescript('''
                CREATE INDEX IF NOT EXISTS idx_materials_grade   ON Materials(grade_id);
                CREATE INDEX IF NOT EXISTS idx_requests_material ON lab_requests(material_id);
                CREATE INDEX IF NOT EXISTS idx_requests_status   ON lab_requests(status, archived);
                ''')


        self.conn.commit()

    def get_materials(self):
        """
        Возвращает список sqlite3.Row с полями:
        id, arrival_date, supplier, order_num, grade, rolling_type,
        size, cert_num, cert_date, batch, heat_num,
        volume_length_mm, volume_weight_kg,
        otk_remarks, needs_lab, to_delete
        (поля, отсутствующие в таблице, подставляются пустыми строками или нулями)
        """
        cur = self.conn.cursor()
        # Определяем существующие колонки в Materials
        existing = {c['name'] for c in cur.execute("PRAGMA table_info(Materials)")}
        fld = lambda name: f"m.{name} AS {name}" if name in existing else f"'' AS {name}"
        select_list = [
            "m.id AS id",
            fld('arrival_date'),
            "s.name AS supplier",
            fld('order_num'),
            "g.grade AS grade",
            "rt.type AS rolling_type",
            fld('size'),
            fld('cert_num'),
            fld('cert_date'),
            "COALESCE(m.batch,'') AS batch" if 'batch' in existing else "'' AS batch",
            fld('heat_num'),
            "COALESCE(m.volume_length_mm,0) AS volume_length_mm"
                if 'volume_length_mm' in existing else "0 AS volume_length_mm",
            "COALESCE(m.volume_weight_kg,0) AS volume_weight_kg"
                if 'volume_weight_kg' in existing else "0 AS volume_weight_kg",
            fld('otk_remarks'),
            fld('needs_lab'),
            "m.cert_scan_path AS cert_scan_path",
            "m.cert_saved_at   AS cert_saved_at",
            fld('to_delete'),
        ]
        query = f'''
            SELECT {', '.join(select_list)}
            FROM Materials m
            LEFT JOIN Suppliers     s  ON m.supplier_id    = s.id
            LEFT JOIN Grades        g  ON m.grade_id       = g.id
            LEFT JOIN RollingTypes  rt ON m.rolling_type_id = rt.id
            ORDER BY m.id
        '''
        cur.execute(query)
        return cur.fetchall()

    def add_material(self, arrival_date, supplier_id, order_num,
                     grade_id, rolling_type_id, size,
                     cert_num, cert_date, batch,
                     heat_num, volume_length_mm, volume_weight_kg):
        cur = self.conn.cursor()
        cur.execute(
            '''
            INSERT INTO Materials(
                arrival_date, supplier_id, order_num,
                grade_id, rolling_type_id, size,
                cert_num, cert_date, batch,
                heat_num, volume_length_mm, volume_weight_kg
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ''',
            (arrival_date, supplier_id, order_num,
             grade_id, rolling_type_id, size,
             cert_num, cert_date, batch,
             heat_num, volume_length_mm, volume_weight_kg)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_material(self, mid, **kwargs):
        fields = ', '.join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [mid]
        cur = self.conn.cursor()
        cur.execute(f'UPDATE Materials SET {fields} WHERE id=?', vals)
        self.conn.commit()

    def get_documents(self, material_id):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM Documents WHERE material_id=?', (material_id,))
        return cur.fetchall()

    def add_document(self, material_id, doc_type, src_path, uploaded_by):
        folder = os.path.join(self.docs_root, str(material_id))
        os.makedirs(folder, exist_ok=True)
        fname = os.path.basename(src_path)
        dst = os.path.join(folder, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(folder, f"{base}_{idx}{ext}")
            idx += 1
        import shutil
        shutil.copy2(src_path, dst)
        upload_date = datetime.datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            '''
            INSERT INTO Documents(
                material_id, doc_type, file_path, upload_date, uploaded_by
            ) VALUES(?,?,?,?,?)
            ''',
            (material_id, doc_type, dst, upload_date, uploaded_by)
        )
        self.conn.commit()
        return cur.lastrowid

    def mark_material_for_deletion(self, material_id):
        """Пометить материал на удаление (soft delete)."""
        self.update_material(material_id, to_delete=1)

    def unmark_material(self, material_id):
        """Снять метку удаления."""
        self.update_material(material_id, to_delete=0)

    def get_marked_for_deletion(self):
        cur = self.conn.cursor()
        cur.execute('''
            SELECT m.id, m.arrival_date, s.name AS supplier, m.order_num
            FROM Materials m
            LEFT JOIN Suppliers s ON m.supplier_id = s.id
            WHERE m.to_delete=1
            ORDER BY m.id
        ''')
        return cur.fetchall()

    def permanently_delete_material(self, material_id):
        """Физически удалить материал и связанные документы."""
        self.conn.execute('DELETE FROM Documents WHERE material_id=?', (material_id,))
        self.conn.execute('DELETE FROM Materials WHERE id=?', (material_id,))
        self.conn.commit()
    def acquire_lock(self, material_id: int, user_login: str) -> bool:
        """
        Попытаться захватить блокировку на material_id.
        Возвращает True, если успешно, False — если уже заблокировано.
        """
        cur = self.conn.cursor()
        # проверяем, есть ли уже запись
        cur.execute("SELECT locked_by FROM RecordLocks WHERE material_id=?", (material_id,))
        row = cur.fetchone()
        if row:
            return False
        now = datetime.datetime.now().isoformat()
        cur.execute(
            "INSERT INTO RecordLocks(material_id, locked_by, locked_at) VALUES(?,?,?)",
            (material_id, user_login, now)
        )
        self.conn.commit()
        return True

    def release_lock(self, material_id: int, user_login: str):
        """
        Освободить блокировку, если её держит этот пользователь.
        """
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM RecordLocks WHERE material_id=? AND locked_by=?",
            (material_id, user_login)
        )
        self.conn.commit()

    def is_locked(self, material_id: int) -> (bool, str):
        """
        Вернёт (True, login) если материал заблокирован другим пользователем,
        иначе (False, '').
        """
        cur = self.conn.cursor()
        cur.execute("SELECT locked_by FROM RecordLocks WHERE material_id=?", (material_id,))
        row = cur.fetchone()
        if row:
            return True, row['locked_by']
        return False, ''

    def close(self):
        if self.conn:
            self.conn.close()
