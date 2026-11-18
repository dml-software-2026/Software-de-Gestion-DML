# tests/test_export_excel.py - #312: descargas en Excel (.xlsx) en vez de CSV
import os
import time
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.excel import armar_xlsx

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


# --- Sin base de datos ---------------------------------------------------

def test_armar_xlsx_formato():
    contenido = armar_xlsx("Hoja de prueba", ["Código", "Descripción", "Fecha", "Cantidad"], [
        ["A000006", "HT TENSION MOTOR GROUP", "2026-11-13", 12],
        ["Ñ-001", "Acentos: ÁÉÍÓÚ", "2026-11-14 10:30:00", 0],
        ["X", None, None, 3],
    ])
    ws = load_workbook(BytesIO(contenido)).active

    assert ws.title == "Hoja de prueba"
    assert [c.value for c in ws[1]] == ["Código", "Descripción", "Fecha", "Cantidad"]
    assert ws["A1"].font.bold
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:D4"
    # Acentos intactos y cantidades como número, no como texto
    assert ws["B3"].value == "Acentos: ÁÉÍÓÚ"
    assert ws["D2"].value == 12 and ws["D3"].value == 0
    # Fechas ISO -> fecha real mostrada dd/mm/aaaa (también con hora)
    assert ws["C2"].value.date() == date(2026, 11, 13)
    assert ws["C2"].number_format == "DD/MM/YYYY"
    assert ws["C3"].value.date() == date(2026, 11, 14)
    assert ws["B4"].value is None


def test_armar_xlsx_sin_filas():
    ws = load_workbook(BytesIO(armar_xlsx("Vacía", ["A", "B"], []))).active
    assert [c.value for c in ws[1]] == ["A", "B"]
    assert ws.max_row == 1


# --- Con base de datos ---------------------------------------------------

@pytest.fixture
def cliente_con_rol():
    """Devuelve una función que loguea un usuario temporal con el rol pedido.
    Los usuarios y su auditoría se borran al final."""
    creados = []

    def _login(rol):
        email = f"test-excel-{rol.lower()}-{int(time.time() * 1000)}@qa.local"
        password = "clave-de-prueba-312"
        with app.app_context():
            db = get_db()
            user_id = db.execute(
                "INSERT INTO users (email, password_hash, nombre, role) VALUES (%s, %s, 'QA #312', %s) RETURNING id",
                (email, generate_password_hash(password), rol),
            ).fetchone()['id']
            db.commit()
        creados.append(user_id)
        client = app.test_client()
        client.post('/login', data={'email': email, 'password': password})
        return client

    app.config['TESTING'] = True
    yield _login
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM logs_auditoria WHERE id_usuario = ANY(%s)", (creados,))
        db.execute("DELETE FROM users WHERE id = ANY(%s)", (creados,))
        db.commit()


def _hoja(resp):
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert ".xlsx" in resp.headers["Content-Disposition"]
    return load_workbook(BytesIO(resp.data)).active


@necesita_db
@pytest.mark.parametrize("rol, columnas", [
    ("ADMIN", ["Código", "Descripción", "Ubicación física", "Cantidad DML", "Estado", "Stock RAYPAC", "Stock Total"]),
    ("DML_ST", ["Código", "Descripción", "Ubicación física", "Cantidad DML", "Estado"]),
    ("DML_REPUESTOS", ["Código", "Descripción", "Ubicación física", "Cantidad DML", "Estado"]),
    # RAYPAC no ve la ubicación física (respuesta 5.2 de David)
    ("RAYPAC", ["Código", "Descripción", "Cantidad DML", "Estado"]),
])
def test_export_stock_columnas_por_rol(cliente_con_rol, rol, columnas):
    ws = _hoja(cliente_con_rol(rol).get("/export/stock.xlsx"))
    assert [c.value for c in ws[1]] == columnas


@necesita_db
def test_export_fichas_y_raypac(cliente_con_rol):
    admin = cliente_con_rol("ADMIN")
    assert _hoja(admin.get("/export/fichas.xlsx"))["A1"].value == "N° Ficha"
    assert _hoja(admin.get("/export/raypac.xlsx"))["A1"].value == "N° Correlativo"


@necesita_db
def test_export_fichas_no_para_raypac(cliente_con_rol):
    resp = cliente_con_rol("RAYPAC").get("/export/fichas.xlsx")
    assert resp.status_code != 200 or resp.mimetype != "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
