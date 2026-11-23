# tests/test_envios_form.py - #337: buscador y barra fija en el form de envío de repuestos
import os

import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


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


@necesita_db
@pytest.mark.parametrize("role", ["ADMIN", "RAYPAC"])
def test_nuevo_envio_tiene_buscador_y_barra_fija(client, role):
    loguear_como(client, role)
    html = client.get("/envios/new").get_data(as_text=True)
    assert 'id="barra-envio"' in html
    assert 'id="buscar-repuesto"' in html
    assert 'id="solo-seleccionados"' in html
    assert 'id="sin-resultados"' in html
    # Guardar arriba (barra) y al pie
    assert html.count("Guardar envío") == 2
    # La barra va antes de la lista
    assert html.index('id="barra-envio"') < html.index('id="tabla-repuestos"')


@necesita_db
def test_admin_carga_no_listados_desde_arriba(client):
    loguear_como(client, "ADMIN")
    html = client.get("/envios/new").get_data(as_text=True)
    assert 'id="btn-no-listado"' in html
    assert html.index('id="repuestos-adicionales"') < html.index('id="tabla-repuestos"')


@necesita_db
def test_raypac_no_ve_no_listados(client):
    # Los códigos nuevos los da de alta solo DML (pedido de David)
    loguear_como(client, "RAYPAC")
    html = client.get("/envios/new").get_data(as_text=True)
    assert 'id="btn-no-listado"' not in html
    assert 'id="repuestos-adicionales"' not in html
    assert "Pedile a DML que lo dé de alta" in html
