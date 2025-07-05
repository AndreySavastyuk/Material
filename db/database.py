# db/database.py

import sqlite3
import os
import datetime
import hashlib
import bcrypt
import logging
from typing import Optional, Dict, Any, Tuple, List
from config import load_config

logger = logging.getLogger(__name__)

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
        self._materials_repository = None

    @property
    def materials_repository(self):
        """Ленивое создание MaterialsRepository."""
        if self._materials_repository is None and self.conn:
            try:
                from repositories.materials_repository import MaterialsRepository
                self._materials_repository = MaterialsRepository(self.conn, self.docs_root)
                logger.info("MaterialsRepository инициализирован")
            except ImportError as e:
                logger.warning(f"Не удалось загрузить MaterialsRepository: {e}")
        return self._materials_repository

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
            password_bcrypt TEXT,
            password_type TEXT DEFAULT 'sha256',
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

        # Добавляем поля для bcrypt в таблицу Users
        existing_users = {row['name'] for row in self.conn.execute("PRAGMA table_info(Users)")}
        if 'password_bcrypt' not in existing_users:
            self.conn.execute("ALTER TABLE Users ADD COLUMN password_bcrypt TEXT")
        if 'password_type' not in existing_users:
            self.conn.execute("ALTER TABLE Users ADD COLUMN password_type TEXT DEFAULT 'sha256'")

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
            self.create_admin_user()

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

    def create_admin_user(self):
        """
        Создает администратора с паролем 'admin' используя bcrypt.
        """
        try:
            # Создаем bcrypt хеш для пароля 'admin'
            password_bcrypt = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Создаем SHA256 хеш для обратной совместимости
            password_sha256 = hashlib.sha256('admin'.encode('utf-8')).hexdigest()
            
            cur = self.conn.cursor()
            cur.execute(
                """INSERT INTO Users(login, password_hash, password_bcrypt, password_type, role, name, salt) 
                   VALUES(?,?,?,?,?,?,?)""",
                ('admin', password_sha256, password_bcrypt, 'bcrypt', 'Администратор', 'Админ', '')
            )
            self.conn.commit()
            logger.info("Создан пользователь admin с bcrypt паролем")
        except Exception as e:
            logger.error(f"Ошибка при создании администратора: {e}")
            # Fallback к старому способу
            pwd = hashlib.sha256('admin'.encode('utf-8')).hexdigest()
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO Users(login, password_hash, role, name, salt) VALUES(?,?,?,?,?)",
                ('admin', pwd, 'Администратор', 'Админ', '')
            )
            self.conn.commit()

    def verify_user(self, login: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет пароль пользователя с обратной совместимостью.
        Сначала проверяет bcrypt, потом SHA256.
        
        Args:
            login: Логин пользователя
            password: Пароль для проверки
            
        Returns:
            Словарь с данными пользователя или None, если авторизация не удалась
        """
        cur = self.conn.cursor()
        cur.execute(
            """SELECT id, login, password_hash, password_bcrypt, password_type, role, name 
               FROM Users WHERE login=?""", 
            (login,)
        )
        row = cur.fetchone()
        
        if not row:
            logger.warning(f"Пользователь {login} не найден")
            return None
            
        user_data = {
            'id': row['id'],
            'login': row['login'],
            'role': row['role'],
            'name': row['name']
        }
        
        password_type = row['password_type'] or 'sha256'
        
        # Проверяем bcrypt пароль
        if password_type == 'bcrypt' and row['password_bcrypt']:
            try:
                if bcrypt.checkpw(password.encode('utf-8'), row['password_bcrypt'].encode('utf-8')):
                    logger.info(f"Успешная авторизация пользователя {login} (bcrypt)")
                    return user_data
            except Exception as e:
                logger.error(f"Ошибка при проверке bcrypt пароля для {login}: {e}")
        
        # Проверяем SHA256 пароль (обратная совместимость)
        if row['password_hash']:
            sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if sha256_hash == row['password_hash']:
                logger.info(f"Успешная авторизация пользователя {login} (SHA256) - рекомендуется обновить пароль")
                
                # Автоматически обновляем пароль на bcrypt
                self._upgrade_password_to_bcrypt(row['id'], password)
                
                return user_data
        
        logger.warning(f"Неверный пароль для пользователя {login}")
        return None

    def _upgrade_password_to_bcrypt(self, user_id: int, password: str) -> None:
        """
        Обновляет пароль пользователя на bcrypt.
        
        Args:
            user_id: ID пользователя
            password: Открытый пароль
        """
        try:
            password_bcrypt = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE Users SET password_bcrypt = ?, password_type = 'bcrypt' WHERE id = ?",
                (password_bcrypt, user_id)
            )
            self.conn.commit()
            logger.info(f"Пароль пользователя (ID: {user_id}) обновлен на bcrypt")
        except Exception as e:
            logger.error(f"Ошибка при обновлении пароля на bcrypt для пользователя {user_id}: {e}")

    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """
        Изменяет пароль пользователя.
        
        Args:
            user_id: ID пользователя
            old_password: Текущий пароль
            new_password: Новый пароль
            
        Returns:
            True если пароль успешно изменен, False в противном случае
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT login, password_hash, password_bcrypt, password_type FROM Users WHERE id=?",
            (user_id,)
        )
        row = cur.fetchone()
        
        if not row:
            logger.error(f"Пользователь с ID {user_id} не найден")
            return False
        
        login = row['login']
        
        # Проверяем текущий пароль
        if not self._verify_password(row, old_password):
            logger.warning(f"Неверный текущий пароль для пользователя {login}")
            return False
        
        # Устанавливаем новый пароль
        try:
            new_password_bcrypt = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute(
                "UPDATE Users SET password_bcrypt = ?, password_type = 'bcrypt', password_hash = '' WHERE id = ?",
                (new_password_bcrypt, user_id)
            )
            self.conn.commit()
            logger.info(f"Пароль пользователя {login} успешно изменен")
            return True
        except Exception as e:
            logger.error(f"Ошибка при изменении пароля для пользователя {login}: {e}")
            return False

    def _verify_password(self, user_row: sqlite3.Row, password: str) -> bool:
        """
        Проверяет пароль пользователя по данным из БД.
        
        Args:
            user_row: Строка с данными пользователя из БД
            password: Пароль для проверки
            
        Returns:
            True если пароль корректен, False в противном случае
        """
        password_type = user_row['password_type'] or 'sha256'
        
        # Проверяем bcrypt пароль
        if password_type == 'bcrypt' and user_row['password_bcrypt']:
            try:
                return bcrypt.checkpw(password.encode('utf-8'), user_row['password_bcrypt'].encode('utf-8'))
            except Exception:
                return False
        
        # Проверяем SHA256 пароль (обратная совместимость)
        if user_row['password_hash']:
            sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            return sha256_hash == user_row['password_hash']
        
        return False

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные пользователя по логину.
        
        Args:
            login: Логин пользователя
            
        Returns:
            Словарь с данными пользователя или None
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, login, role, name FROM Users WHERE login=?",
            (login,)
        )
        row = cur.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'login': row['login'],
                'role': row['role'],
                'name': row['name']
            }
        return None

    def create_user(self, login: str, password: str, role: str, name: str = None) -> Optional[int]:
        """
        Создает нового пользователя.
        
        Args:
            login: Логин пользователя
            password: Пароль
            role: Роль пользователя
            name: Имя пользователя (опционально)
            
        Returns:
            ID созданного пользователя или None в случае ошибки
        """
        try:
            # Создаем bcrypt хеш
            password_bcrypt = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            cur = self.conn.cursor()
            cur.execute(
                """INSERT INTO Users(login, password_hash, password_bcrypt, password_type, role, name, salt) 
                   VALUES(?,?,?,?,?,?,?)""",
                (login, '', password_bcrypt, 'bcrypt', role, name or login, '')
            )
            self.conn.commit()
            
            user_id = cur.lastrowid
            logger.info(f"Создан пользователь {login} с ID {user_id}")
            return user_id
            
        except sqlite3.IntegrityError:
            logger.error(f"Пользователь с логином {login} уже существует")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя {login}: {e}")
            return None

    def get_materials(self):
        """
        Возвращает список материалов с данными из связанных таблиц.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.get_materials_with_relations()
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
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
        """
        Добавляет новый материал.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                material_data = {
                    'arrival_date': arrival_date,
                    'supplier_id': supplier_id,
                    'order_num': order_num,
                    'grade_id': grade_id,
                    'rolling_type_id': rolling_type_id,
                    'size': size,
                    'cert_num': cert_num,
                    'cert_date': cert_date,
                    'batch': batch,
                    'heat_num': heat_num,
                    'volume_length_mm': volume_length_mm,
                    'volume_weight_kg': volume_weight_kg
                }
                return self.materials_repository.create_material(material_data)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
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
        """
        Обновляет материал.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.update_material(mid, kwargs)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        fields = ', '.join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [mid]
        cur = self.conn.cursor()
        cur.execute(f'UPDATE Materials SET {fields} WHERE id=?', vals)
        self.conn.commit()

    def get_documents(self, material_id):
        """
        Получает документы материала.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.get_documents(material_id)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM Documents WHERE material_id=?', (material_id,))
        return cur.fetchall()

    def add_document(self, material_id, doc_type, src_path, uploaded_by):
        """
        Добавляет документ к материалу.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.add_document(material_id, doc_type, src_path, uploaded_by)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
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
        """
        Помечает материал на удаление (soft delete).
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.mark_for_deletion(material_id)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        self.update_material(material_id, to_delete=1)

    def unmark_material(self, material_id):
        """
        Снимает метку удаления с материала.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.unmark_for_deletion(material_id)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        self.update_material(material_id, to_delete=0)

    def get_marked_for_deletion(self):
        """
        Получает материалы, помеченные на удаление.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.get_marked_for_deletion()
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
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
        """
        Физически удаляет материал и связанные документы.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.permanently_delete_material(material_id)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        self.conn.execute('DELETE FROM Documents WHERE material_id=?', (material_id,))
        self.conn.execute('DELETE FROM Materials WHERE id=?', (material_id,))
        self.conn.commit()

    def acquire_lock(self, material_id: int, user_login: str) -> bool:
        """
        Захватывает блокировку на материал.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.acquire_lock(material_id, user_login)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        cur = self.conn.cursor()
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
        Освобождает блокировку материала.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.release_lock(material_id, user_login)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM RecordLocks WHERE material_id=? AND locked_by=?",
            (material_id, user_login)
        )
        self.conn.commit()

    def is_locked(self, material_id: int) -> (bool, str):
        """
        Проверяет, заблокирован ли материал.
        Использует MaterialsRepository если доступен, иначе старый метод.
        """
        if self.materials_repository:
            try:
                return self.materials_repository.is_locked(material_id)
            except Exception as e:
                logger.error(f"Ошибка в MaterialsRepository: {e}")
                # Fallback к старому методу
                pass
        
        # Старый метод как fallback
        cur = self.conn.cursor()
        cur.execute("SELECT locked_by FROM RecordLocks WHERE material_id=?", (material_id,))
        row = cur.fetchone()
        if row:
            return True, row['locked_by']
        return False, ''

    # ============ Методы для работы с ролями и правами ============
    
    def get_user_roles(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает все активные роли пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список ролей пользователя
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT r.id, r.name, r.display_name, r.description, ur.assigned_at, ur.expires_at
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = ? AND ur.is_active = 1
            AND (ur.expires_at IS NULL OR ur.expires_at > datetime('now'))
            ORDER BY r.name
        ''', (user_id,))
        
        roles = []
        for row in cur.fetchall():
            roles.append({
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'assigned_at': row['assigned_at'],
                'expires_at': row['expires_at']
            })
        return roles

    def get_user_permissions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает все права пользователя через его роли.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список прав пользователя
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT DISTINCT p.id, p.name, p.display_name, p.description, p.category
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = ? AND ur.is_active = 1
            AND (ur.expires_at IS NULL OR ur.expires_at > datetime('now'))
            ORDER BY p.category, p.name
        ''', (user_id,))
        
        permissions = []
        for row in cur.fetchall():
            permissions.append({
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'category': row['category']
            })
        return permissions

    def user_has_permission(self, user_id: int, permission_name: str) -> bool:
        """
        Проверяет, есть ли у пользователя указанное право.
        
        Args:
            user_id: ID пользователя
            permission_name: Название права (например, 'materials.create')
            
        Returns:
            True если право есть, False в противном случае
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT COUNT(*) as count
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = ? AND p.name = ? AND ur.is_active = 1
            AND (ur.expires_at IS NULL OR ur.expires_at > datetime('now'))
        ''', (user_id, permission_name))
        
        row = cur.fetchone()
        return row['count'] > 0

    def get_all_roles(self) -> List[Dict[str, Any]]:
        """
        Получает все роли в системе.
        
        Returns:
            Список всех ролей
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT id, name, display_name, description, is_system, created_at
            FROM roles
            ORDER BY name
        ''')
        
        roles = []
        for row in cur.fetchall():
            roles.append({
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'is_system': row['is_system'],
                'created_at': row['created_at']
            })
        return roles

    def get_all_permissions(self) -> List[Dict[str, Any]]:
        """
        Получает все права в системе.
        
        Returns:
            Список всех прав
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT id, name, display_name, description, category, is_system, created_at
            FROM permissions
            ORDER BY category, name
        ''')
        
        permissions = []
        for row in cur.fetchall():
            permissions.append({
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'category': row['category'],
                'is_system': row['is_system'],
                'created_at': row['created_at']
            })
        return permissions

    def get_role_permissions(self, role_id: int) -> List[Dict[str, Any]]:
        """
        Получает все права роли.
        
        Args:
            role_id: ID роли
            
        Returns:
            Список прав роли
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT p.id, p.name, p.display_name, p.description, p.category
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id = ?
            ORDER BY p.category, p.name
        ''', (role_id,))
        
        permissions = []
        for row in cur.fetchall():
            permissions.append({
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'category': row['category']
            })
        return permissions

    def assign_role_to_user(self, user_id: int, role_id: int, assigned_by: int = None, expires_at: str = None) -> bool:
        """
        Назначает роль пользователю.
        
        Args:
            user_id: ID пользователя
            role_id: ID роли
            assigned_by: ID пользователя, который назначает роль
            expires_at: Дата истечения роли (опционально)
            
        Returns:
            True если роль назначена успешно, False в противном случае
        """
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO user_roles (user_id, role_id, assigned_by, expires_at, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (user_id, role_id, assigned_by, expires_at))
            self.conn.commit()
            
            # Логируем назначение роли
            role_name = self.get_role_by_id(role_id)['name'] if self.get_role_by_id(role_id) else 'Unknown'
            user_name = self.get_user_by_id(user_id)['login'] if self.get_user_by_id(user_id) else 'Unknown'
            logger.info(f"Роль {role_name} назначена пользователю {user_name}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при назначении роли: {e}")
            return False

    def revoke_role_from_user(self, user_id: int, role_id: int) -> bool:
        """
        Отзывает роль у пользователя.
        
        Args:
            user_id: ID пользователя
            role_id: ID роли
            
        Returns:
            True если роль отозвана успешно, False в противном случае
        """
        try:
            cur = self.conn.cursor()
            cur.execute('''
                UPDATE user_roles 
                SET is_active = 0 
                WHERE user_id = ? AND role_id = ?
            ''', (user_id, role_id))
            self.conn.commit()
            
            # Логируем отзыв роли
            role_name = self.get_role_by_id(role_id)['name'] if self.get_role_by_id(role_id) else 'Unknown'
            user_name = self.get_user_by_id(user_id)['login'] if self.get_user_by_id(user_id) else 'Unknown'
            logger.info(f"Роль {role_name} отозвана у пользователя {user_name}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при отзыве роли: {e}")
            return False

    def get_role_by_id(self, role_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает роль по ID.
        
        Args:
            role_id: ID роли
            
        Returns:
            Данные роли или None
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT id, name, display_name, description, is_system, created_at
            FROM roles
            WHERE id = ?
        ''', (role_id,))
        
        row = cur.fetchone()
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'is_system': row['is_system'],
                'created_at': row['created_at']
            }
        return None

    def get_role_by_name(self, role_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает роль по имени.
        
        Args:
            role_name: Имя роли
            
        Returns:
            Данные роли или None
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT id, name, display_name, description, is_system, created_at
            FROM roles
            WHERE name = ?
        ''', (role_name,))
        
        row = cur.fetchone()
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'is_system': row['is_system'],
                'created_at': row['created_at']
            }
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает пользователя по ID.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Данные пользователя или None
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT id, login, role, name
            FROM Users
            WHERE id = ?
        ''', (user_id,))
        
        row = cur.fetchone()
        if row:
            return {
                'id': row['id'],
                'login': row['login'],
                'role': row['role'],
                'name': row['name']
            }
        return None

    def create_role(self, name: str, display_name: str, description: str = None) -> Optional[int]:
        """
        Создает новую роль.
        
        Args:
            name: Имя роли (уникальное)
            display_name: Отображаемое имя роли
            description: Описание роли
            
        Returns:
            ID созданной роли или None в случае ошибки
        """
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT INTO roles (name, display_name, description, is_system)
                VALUES (?, ?, ?, 0)
            ''', (name, display_name, description))
            self.conn.commit()
            
            role_id = cur.lastrowid
            logger.info(f"Создана роль {name} с ID {role_id}")
            return role_id
            
        except sqlite3.IntegrityError:
            logger.error(f"Роль с именем {name} уже существует")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании роли {name}: {e}")
            return None

    def create_permission(self, name: str, display_name: str, description: str = None, category: str = 'custom') -> Optional[int]:
        """
        Создает новое право.
        
        Args:
            name: Имя права (уникальное)
            display_name: Отображаемое имя права
            description: Описание права
            category: Категория права
            
        Returns:
            ID созданного права или None в случае ошибки
        """
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT INTO permissions (name, display_name, description, category, is_system)
                VALUES (?, ?, ?, ?, 0)
            ''', (name, display_name, description, category))
            self.conn.commit()
            
            permission_id = cur.lastrowid
            logger.info(f"Создано право {name} с ID {permission_id}")
            return permission_id
            
        except sqlite3.IntegrityError:
            logger.error(f"Право с именем {name} уже существует")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании права {name}: {e}")
            return None

    def assign_permission_to_role(self, role_id: int, permission_id: int) -> bool:
        """
        Назначает право роли.
        
        Args:
            role_id: ID роли
            permission_id: ID права
            
        Returns:
            True если право назначено успешно, False в противном случае
        """
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (role_id, permission_id))
            self.conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при назначении права роли: {e}")
            return False

    def revoke_permission_from_role(self, role_id: int, permission_id: int) -> bool:
        """
        Отзывает право у роли.
        
        Args:
            role_id: ID роли
            permission_id: ID права
            
        Returns:
            True если право отозвано успешно, False в противном случае
        """
        try:
            cur = self.conn.cursor()
            cur.execute('''
                DELETE FROM role_permissions
                WHERE role_id = ? AND permission_id = ?
            ''', (role_id, permission_id))
            self.conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при отзыве права у роли: {e}")
            return False

    def get_permissions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Получает права по категории.
        
        Args:
            category: Категория прав
            
        Returns:
            Список прав в категории
        """
        cur = self.conn.cursor()
        cur.execute('''
            SELECT id, name, display_name, description, category, is_system
            FROM permissions
            WHERE category = ?
            ORDER BY name
        ''', (category,))
        
        permissions = []
        for row in cur.fetchall():
            permissions.append({
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'category': row['category'],
                'is_system': row['is_system']
            })
        return permissions

    def get_permission_categories(self) -> List[str]:
        """
        Получает все категории прав.
        
        Returns:
            Список категорий прав
        """
        cur = self.conn.cursor()
        cur.execute('SELECT DISTINCT category FROM permissions ORDER BY category')
        return [row['category'] for row in cur.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()
