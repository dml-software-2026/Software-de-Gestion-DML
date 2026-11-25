# tests/test_pago_fichas.py - #372: N° FACTURA, PAGO RAYPAC y PAGO TECNICO en /dml/entregadas
import os

import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)

CAMPOS = "numero_factura, pago_raypac, pago_tecnico"


@pytest.fixture(scope="module", autouse=True)
def base_migrada():
    """Las migraciones corren en el primer request (before_request de app.py),
    no al importar la app: sin esto, en una base sin las columnas nuevas (ej.
    la del CI) los tests las consultan antes de que existan."""
    if os.getenv("DATABASE_URL"):
        with app.test_client() as c:
            c.get("/login")


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def loguear_como(client, role):
    with app.app_context():
        user = get_db().execute("SELECT * FROM users WHERE role = %s ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        pytest.skip(f"No hay usuario con rol {role} en la base")
    with client.session_transaction() as sess:
        sess['user_id'] = user['id']


def pago(ficha_id):
    with app.app_context():
        return dict(get_db().execute(f"SELECT {CAMPOS} FROM dml_fichas WHERE id = %s", (ficha_id,)).fetchone())


@pytest.fixture
def ficha():
    """Una ficha cerrada (ya recibida por RAYPAC): el pago se carga después de la
    entrega, sin desbloquearla. Al final se le devuelven los valores originales."""
    with app.app_context():
        fila = get_db().execute(
            "SELECT id FROM dml_fichas WHERE is_closed = TRUE ORDER BY id DESC LIMIT 1").fetchone()
    if not fila:
        pytest.skip("No hay fichas cerradas en la base")
    original = pago(fila['id'])
    yield fila['id']
    with app.app_context():
        db = get_db()
        db.execute("UPDATE dml_fichas SET numero_factura = %s, pago_raypac = %s, pago_tecnico = %s WHERE id = %s",
                   (original['numero_factura'], original['pago_raypac'], original['pago_tecnico'], fila['id']))
        db.commit()


@necesita_db
def test_ficha_nueva_queda_en_debe():
    with app.app_context():
        columnas = {r['column_name']: r['column_default'] for r in get_db().execute(
            "SELECT column_name, column_default FROM information_schema.columns "
            "WHERE table_name = 'dml_fichas' AND column_name IN ('numero_factura', 'pago_raypac', 'pago_tecnico')")}
    assert set(columnas) == {'numero_factura', 'pago_raypac', 'pago_tecnico'}
    assert "DEBE" in columnas['pago_raypac'] and "DEBE" in columnas['pago_tecnico']


@necesita_db
@pytest.mark.parametrize("role", ["ADMIN", "DML_ST"])
def test_admin_y_tecnico_cambian_el_pago_con_la_ficha_cerrada(client, ficha, role):
    loguear_como(client, role)
    for campo, valor in [("pago_raypac", "PAGADO"), ("pago_tecnico", "PAGADO"),
                         ("numero_factura", "  A-0001-  00012345 ")]:
        r = client.post(f"/dml/{ficha}/pago", data={"campo": campo, "valor": valor})
        assert r.status_code == 200 and r.get_json()["ok"]
    assert pago(ficha) == {"numero_factura": "A-0001- 00012345", "pago_raypac": "PAGADO", "pago_tecnico": "PAGADO"}

    # Volver a DEBE y borrar la factura
    client.post(f"/dml/{ficha}/pago", data={"campo": "pago_raypac", "valor": "DEBE"})
    client.post(f"/dml/{ficha}/pago", data={"campo": "numero_factura", "valor": ""})
    assert pago(ficha) == {"numero_factura": None, "pago_raypac": "DEBE", "pago_tecnico": "PAGADO"}


@necesita_db
@pytest.mark.parametrize("campo, valor", [
    ("pago_raypac", "pagado"), ("pago_tecnico", ""), ("numero_factura", "1" * 51),
    ("estado_reparacion", "REPARADA"), ("is_closed", "false"),
])
def test_valores_o_campos_invalidos_no_se_guardan(client, ficha, campo, valor):
    loguear_como(client, "ADMIN")
    antes = pago(ficha)
    r = client.post(f"/dml/{ficha}/pago", data={"campo": campo, "valor": valor})
    assert r.status_code == 400 and not r.get_json()["ok"]
    assert pago(ficha) == antes


@necesita_db
@pytest.mark.parametrize("role", ["RAYPAC", "DML_REPUESTOS"])
def test_raypac_y_repuestos_no_cambian_el_pago(client, ficha, role):
    loguear_como(client, role)
    antes = pago(ficha)
    assert client.post(f"/dml/{ficha}/pago", data={"campo": "pago_raypac", "valor": "PAGADO"}).status_code == 302
    assert pago(ficha) == antes


@necesita_db
def test_columnas_en_entregadas_segun_el_rol(client, ficha):
    loguear_como(client, "DML_ST")
    html = client.get("/dml/entregadas").get_data(as_text=True)
    assert "Pago Técnico" in html and 'data-campo="pago_tecnico"' in html and 'data-campo="numero_factura"' in html

    # RAYPAC: el pago es solo de DML, no ve ninguna de las 3 columnas (pedido del cliente, 25/11)
    loguear_como(client, "RAYPAC")
    html = client.get("/dml/entregadas").get_data(as_text=True)
    assert "N° Factura" not in html and "Pago RAYPAC" not in html
    assert "Pago Técnico" not in html and "js-pago" not in html


@necesita_db
def test_pago_de_una_ficha_que_no_existe(client):
    loguear_como(client, "ADMIN")
    r = client.post("/dml/999999999/pago", data={"campo": "pago_raypac", "valor": "PAGADO"})
    assert r.status_code == 404
