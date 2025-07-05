# gui/lab/pdf_generator.py

import json
import os
import datetime
import shutil
from fpdf import FPDF
from db.database import Database

def generate_pdf_for_request(req_id: int) -> str:

    db = Database().connect()
    cur = db.cursor()
    cur.execute("""
        SELECT
            lr.request_number,
            lr.creation_date,
            lr.tests_json,
            lr.results_json,
            g.grade,
            m.size,
            m.order_num
        FROM lab_requests lr
        JOIN Materials m ON lr.material_id = m.id
        JOIN Grades    g ON m.grade_id     = g.id
        WHERE lr.id = ?
    """, (req_id,))
    row = cur.fetchone()
    if not row:
        db.close()
        return ''

    # распаковываем поля
    req_num = row['request_number']
    created = row['creation_date']
    tests   = json.loads(row['tests_json'])
    results = json.loads(row['results_json'])
    grade   = row['grade']
    size    = row['size']
    order   = row['order_num']

    # папки
    base = r"D:\mes\Лаборатория"
    hier = os.path.join(base, "Заявки на испытания", order.replace('/', '-'), grade)
    common = os.path.join(base, "Заявки общая")
    os.makedirs(hier, exist_ok=True)
    os.makedirs(common, exist_ok=True)

    # имя файла
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"{req_num}_{timestamp}.pdf"
    path_hier  = os.path.join(hier, fname)
    path_common = os.path.join(common, fname)

    # сборка PDF
    pdf = FPDF()
    pdf.add_page()

    # Unicode-шрифт
    font_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__),
                     '..','..','resources','fonts','DejaVuSans.ttf')
    )
    pdf.add_font('DejaVu','', font_path, uni=True)
    pdf.add_font('DejaVu','B', font_path, uni=True)

    pdf.set_font('DejaVu','B',16)
    pdf.cell(0,10, f"Заявка №{req_num}", ln=1)
    pdf.set_font('DejaVu','',12)
    pdf.cell(0,8, f"Дата создания: {created}", ln=1)
    pdf.cell(0,8, f"Заказ: {order}", ln=1)
    pdf.cell(0,8, f"Марка: {grade}", ln=1)
    pdf.cell(0,8, f"Размер: {size} мм", ln=1)
    pdf.ln(4)

    pdf.set_font('DejaVu','B',14)
    pdf.cell(0,8,"Список испытаний:", ln=1)
    pdf.set_font('DejaVu','',12)
    for t in tests:
        pdf.cell(0,6, f"– {t}", ln=1)
    pdf.ln(4)

    pdf.set_font('DejaVu','B',14)
    pdf.cell(0,8,"Результаты:", ln=1)
    pdf.set_font('DejaVu','',12)
    for res in results:
        line = f"{res['name']}: {res.get('result','')} — {res.get('comment','')}"
        pdf.multi_cell(0,6, line)
    pdf.ln(4)

    pdf.set_font('DejaVu','',10)
    pdf.cell(0,8, f"Сгенерировано: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=1)

    # сохраняем
    pdf.output(path_hier)
    shutil.copy2(path_hier, path_common)

    # обновляем в БД путь к последнему PDF (иерархический)
    db.execute(
        "UPDATE lab_requests SET last_pdf_path = ? WHERE id = ?",
        (path_hier, req_id)
    )
    db.commit()
    db.close()
    return path_hier
