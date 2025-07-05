import os
import shutil
from datetime import datetime
from db.database import Database


def save_certificate(db: Database, material_id: int, source_pdf_path: str, docs_root: str) -> str:
    """
    Сохраняет PDF сертификат для указанного материала в двух структурах:
    1. Все сертификаты: docs_root/Все сертификаты/grade/{size} {rolling}
    2. Заказы: docs_root/Заказы/{order_folder}/grade/{size} {rolling}

    Аргументы:
        db: экземпляр Database
        material_id: ID материала
        source_pdf_path: путь к исходному PDF
        docs_root: корневая папка для хранения сертификатов

    Возвращает сообщение о результате сохранения.
    """
    # Получаем материалы и находим нужный
    mats = [dict(row) for row in db.get_materials()]
    mat = next((m for m in mats if m['id'] == material_id), None)
    if not mat:
        raise ValueError(f"Материал с id={material_id} не найден")

    order = mat.get('order_num', '')
    grade = mat.get('grade', '')
    rolling = mat.get('rolling_type', '')
    size = mat.get('size', '')
    heat = mat.get('heat_num', '')
    cert_num = mat.get('cert_num', '')
    supplier = mat.get('supplier', '')
    old_path = mat.get('cert_scan_path', '')

    # Имя папки с размером и видом проката: "{size} {rolling}" (например "23 Круг")
    type_size_folder = f"{size} {rolling}".strip()

    # Структура "Все сертификаты"
    all_root = os.path.join(docs_root, "Все сертификаты")
    path_all = os.path.join(all_root, grade, type_size_folder)
    os.makedirs(path_all, exist_ok=True)

    # Структура "Заказы"
    order_folder = order.replace('/', '-') if order else ''
    if order_folder:
        path_order = os.path.join(docs_root, 'Заказы', order_folder, grade, type_size_folder)
        os.makedirs(path_order, exist_ok=True)
    else:
        path_order = None

    # Удаляем старый файл в заказах
    if old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except OSError:
            pass
    # Удаляем старый файл в "Все сертификаты"
    if old_path:
        old_all = os.path.join(all_root, grade, type_size_folder, os.path.basename(old_path))
        if os.path.exists(old_all):
            try:
                os.remove(old_all)
            except OSError:
                pass

    # Новое имя файла: <size>_<grade>_пл.<heat>_серт.№<cert_num>_(<supplier>_<date>).pdf
    date_str = datetime.now().strftime('%d.%m.%Y')
    filename = f"{size}_{grade}_пл.{heat}_серт.№{cert_num}_(" + f"{supplier}_{date_str}).pdf"

    # Копируем в "Все сертификаты"
    dest_all = os.path.join(path_all, filename)
    shutil.copy2(source_pdf_path, dest_all)

    # Копируем в "Заказы" и сохраняем этот путь в БД, если есть заказ
    if path_order:
        dest_order = os.path.join(path_order, filename)
        shutil.copy2(source_pdf_path, dest_order)
        db_path = dest_order
    else:
        db_path = dest_all

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Обновляем запись в БД
    cert_date = datetime.now().strftime('%Y-%m-%d')
    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db.conn.execute(
        'UPDATE Materials SET cert_scan_path = ?, cert_date = ? WHERE id = ?',
        (db_path, cert_date, material_id)
    )
    # обновляем timestamp загрузки/замены
    db.conn.execute(
        'UPDATE Materials SET cert_saved_at   = ? WHERE id = ?',
        (now_ts, material_id)
    )
    db.conn.commit()

    action = 'обновлен' if old_path else 'загружен'
    return f"Сертификат {action}: {filename}"