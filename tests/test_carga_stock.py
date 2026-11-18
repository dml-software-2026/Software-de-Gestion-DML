# tests/test_carga_stock.py - #310: carga masiva del stock de DML desde la planilla del cliente
import os
import time

import openpyxl
import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.carga_stock import PLANILLA_STOCK, cargar_stock_dml, leer_planilla_stock

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


def armar_planilla(ruta, filas):
    """Planilla con el formato de la de DML: títulos arriba, encabezado CODIGO en la columna C."""
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append([None, None, "DML", "STOCK DE REPUESTOS GENERAL"])
    hoja.append([])
    hoja.append([None, None, None, "ITEM", "TOTAL", "UBICACIÓN ACTUAL", None, None, None, "CODIGO DE UBICACIÓN"])
    hoja.append([None, "TIPO MAQUINA", "CODIGO", None, None, "ESTANTE", "FILA", "POSICION", "BOX"])
    for i, (codigo, item, total, ubicacion) in enumerate(filas, start=1):
        hoja.append([i, "Bateria", codigo, item, total, None, None, None, None, ubicacion])
    libro.save(ruta)
    return str(ruta)


# --- Sin base de datos ---------------------------------------------------

def test_lee_la_planilla_y_normaliza(tmp_path):
    ruta = armar_planilla(tmp_path / "stock.xlsx", [
        ("A000006", "HT TENSION MOTOR GROUP", 10, "E05-F05-B02"),
        (" b600013l ", "  CIRCLIP   ", 3, "E03 -F07 -PB -B04"),
        ("A000179", "AGOTADO", 0, "uso taller"),
        ("A000180", "TOTAL DECIMAL ENTERO", 7.0, None),
        (None, None, None, None),  # fila vacía en el medio
    ])
    filas, errores = leer_planilla_stock(ruta)
    assert errores == []
    assert [(f["codigo"], f["item"], f["cantidad"], f["ubicacion_fisica"]) for f in filas] == [
        ("A000006", "HT TENSION MOTOR GROUP", 10, "E05-F05-B02"),
        ("B600013L", "CIRCLIP", 3, "E03-F07-PB-B04"),
        ("A000179", "AGOTADO", 0, "USO TALLER"),  # el 0 es válido: queda agotado
        ("A000180", "TOTAL DECIMAL ENTERO", 7, "SIN UBICACIÓN"),
    ]


def test_filas_invalidas_se_informan_y_no_se_cargan(tmp_path):
    ruta = armar_planilla(tmp_path / "stock.xlsx", [
        ("A000001", "OK", 1, "E01-F01"),
        ("A000002", None, 1, "E01-F01"),
        ("A000003", "VACIA", None, "E01-F01"),
        ("A000004", "NEGATIVA", -2, "E01-F01"),
        ("A000005", "DECIMAL", 1.5, "E01-F01"),
        ("A000006", "TEXTO", "dos", "E01-F01"),
        ("a000001", "REPETIDO", 4, "E01-F01"),
    ])
    filas, errores = leer_planilla_stock(ruta)
    assert [f["codigo"] for f in filas] == ["A000001"]
    assert [(fila, codigo) for fila, codigo, _ in errores] == [
        (6, "A000002"), (7, "A000003"), (8, "A000004"), (9, "A000005"), (10, "A000006"), (11, "A000001"),
    ]
    assert "fila 5" in errores[-1][2]


def test_planilla_sin_encabezado_falla(tmp_path):
    libro = openpyxl.Workbook()
    libro.active.append(["cualquier", "cosa"])
    libro.save(tmp_path / "otra.xlsx")
    with pytest.raises(ValueError):
        leer_planilla_stock(str(tmp_path / "otra.xlsx"))


def test_planilla_del_cliente_se_lee_entera():
    """La planilla del repo (stock al 31/08/2026): 275 repuestos, todos con ubicación."""
    filas, errores = leer_planilla_stock(PLANILLA_STOCK)
    assert errores == []
    assert len(filas) == 275
    assert sum(1 for f in filas if f["cantidad"] == 0) == 7
    assert "B600013L" in {f["codigo"] for f in filas}


# --- Con base de datos ---------------------------------------------------

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def loguear_como(client, role):
    with app.app_context():
        user = get_db().execute("SELECT id FROM users WHERE role = %s ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        pytest.skip(f"No hay usuario con rol {role} en la base")
    with client.session_transaction() as sess:
        sess['user_id'] = user['id']


@pytest.fixture
def codigos(tmp_path):
    """Tres códigos de prueba: uno existente que sale en la planilla, uno nuevo y uno existente que no sale.

    La planilla de prueba solo tiene estos códigos, así que la carga no toca los repuestos reales.
    Se borra todo al final, pase o falle el test.
    """
    base = f"TEST-CARGA-{int(time.time() * 1000)}"
    existente, nuevo, ajeno = f"{base}-E", f"{base}-N", f"{base}-A"
    with app.app_context():
        db = get_db()
        numero = db.execute("SELECT MAX(numero) AS max FROM matriz_repuestos").fetchone()['max'] or 0
        for i, codigo in enumerate([existente, ajeno], start=1):
            db.execute("""
                INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                VALUES (%s, %s, 'Repuesto de prueba QA', 5, 5, 'DML')
            """, (numero + i, codigo))
            db.execute("""
                INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                VALUES (%s, 'DML', 5, 'E01-F01')
            """, (codigo,))
        db.commit()

    app.config["PLANILLA_STOCK"] = armar_planilla(tmp_path / "stock.xlsx", [
        (existente.lower(), "Repuesto de prueba QA (planilla)", 0, "e09 -f09 -b09"),
        (nuevo, "Repuesto de prueba QA nuevo", 4, "E08-F08"),
    ])
    yield existente, nuevo, ajeno
    app.config.pop("PLANILLA_STOCK", None)
    with app.app_context():
        db = get_db()
        for codigo in (existente, nuevo, ajeno):
            db.execute("DELETE FROM stock_ubicaciones WHERE codigo_repuesto = %s", (codigo,))
            db.execute("DELETE FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,))
        db.commit()


def stock_dml(codigo):
    with app.app_context():
        return get_db().execute("""
            SELECT su.cantidad, su.codigo_ubicacion_fisica, m.item, m.cantidad_actual
            FROM stock_ubicaciones su JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
            WHERE su.codigo_repuesto = %s AND su.ubicacion = 'DML'
        """, (codigo,)).fetchone()


@necesita_db
def test_abrir_la_pantalla_no_carga_nada(client, codigos):
    existente, nuevo, _ = codigos
    loguear_como(client, "ADMIN")
    html = client.get("/admin/cargar-stock-csv").get_data(as_text=True)
    assert "Cargar stock desde la planilla" in html
    assert '<form method="post"' in html
    assert stock_dml(existente)['cantidad'] == 5
    assert stock_dml(nuevo) is None


@necesita_db
@pytest.mark.parametrize("role", ["DML_ST", "DML_REPUESTOS", "RAYPAC"])
def test_solo_admin_puede_cargar(client, codigos, role):
    existente, _, _ = codigos
    loguear_como(client, role)
    client.post("/admin/cargar-stock-csv")
    assert stock_dml(existente)['cantidad'] == 5


@necesita_db
def test_carga_pisa_crea_y_no_toca_lo_ajeno(client, codigos):
    existente, nuevo, ajeno = codigos
    loguear_como(client, "ADMIN")
    html = client.post("/admin/cargar-stock-csv").get_data(as_text=True)
    assert "Carga completada" in html
    assert nuevo in html

    # Existente: queda en 0 (no se saltea) con la ubicación normalizada, también en la matriz
    fila = stock_dml(existente)
    assert (fila['cantidad'], fila['codigo_ubicacion_fisica']) == (0, "E09-F09-B09")
    assert (fila['item'], fila['cantidad_actual']) == ("Repuesto de prueba QA (planilla)", 0)

    # Nuevo: se da de alta en la matriz y en DML
    fila = stock_dml(nuevo)
    assert (fila['cantidad'], fila['codigo_ubicacion_fisica'], fila['cantidad_actual']) == (4, "E08-F08", 4)

    # Ajeno (no está en la planilla): igual que antes
    fila = stock_dml(ajeno)
    assert (fila['cantidad'], fila['codigo_ubicacion_fisica']) == (5, "E01-F01")


class _ContadorDeConsultas:
    """Envuelve la conexión y cuenta cuántas consultas manda a la base."""

    def __init__(self, db):
        self.db, self.consultas = db, 0

    def cursor(self, *args, **kwargs):
        contador, cur = self, self.db.cursor(*args, **kwargs)

        class Cursor:
            def execute(self, *a, **k):
                contador.consultas += 1
                return cur.execute(*a, **k)

            def __getattr__(self, nombre):
                return getattr(cur, nombre)
        return Cursor()


@necesita_db
def test_la_carga_completa_usa_pocas_consultas():
    """En Render cada consulta a Supabase tarda ~0,2 s: repuesto por repuesto, la carga de la
    planilla real (275 filas) pasaba de los 30 s de gunicorn y se cortaba. Tiene que ir en bloque."""
    filas, _ = leer_planilla_stock(PLANILLA_STOCK)
    with app.app_context():
        db = get_db()
        contador = _ContadorDeConsultas(db)
        try:
            resultados = cargar_stock_dml(contador, filas)
        finally:
            db.rollback()  # no deja nada cargado
    assert len(resultados) == len(filas) == 275
    assert contador.consultas <= 6
