# tests/test_ingreso_otra.py - #340: modelo "OTRA" (cargador, batería suelta) en Nuevo ingreso
import os
import time

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


@pytest.fixture
def numero_serie():
    """N° de serie único; al final se borra lo que se haya creado con él, pase o falle el test."""
    numero = f"TEST-OTRA-{int(time.time() * 1000)}"
    yield numero
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM raypac_entries WHERE numero_serie = %s", (numero,))
        db.commit()


def datos_ingreso(numero_serie, **cambios):
    datos = {
        'tipo_solicitud': 'REPARACIÓN',
        'cliente': 'Cliente de Prueba QA',
        'numero_serie': numero_serie,
        'modelo_maquina': 'ITA10',
        'tipo_maquina': 'A BATERIA',
        'comercial': 'Ezequiel Pacheco',
        'mail_comercial': 'ezequiel.pacheco@raypac.net',
    }
    datos.update(cambios)
    return datos


def ingreso(numero_serie):
    with app.app_context():
        return get_db().execute(
            "SELECT id, modelo_maquina, tipo_maquina FROM raypac_entries WHERE numero_serie = %s", (numero_serie,)
        ).fetchone()


@necesita_db
def test_formulario_ofrece_otra(client):
    loguear_como(client, "RAYPAC")
    html = client.get("/raypac/new").get_data(as_text=True)
    assert '<option value="OTRA"' in html
    assert 'id="modelo_otra"' in html
    assert '<option value="OTRO"' not in html  # una sola opción: el tipo OTRO suelto ya no se ofrece


@necesita_db
def test_otra_guarda_lo_que_se_envia(client, numero_serie):
    loguear_como(client, "RAYPAC")
    # El tipo que venga se ignora: con OTRA queda OTRO
    client.post("/raypac/new", data=datos_ingreso(numero_serie, modelo_maquina="OTRA", tipo_maquina="",
                                                  modelo_otra="  cargador   ita 18v "))
    fila = ingreso(numero_serie)
    assert (fila['modelo_maquina'], fila['tipo_maquina']) == ("OTRA: CARGADOR ITA 18V", "OTRO")


@necesita_db
@pytest.mark.parametrize("texto", ["", "   ", "X" * 61])
def test_otra_sin_texto_o_muy_largo_no_se_guarda(client, numero_serie, texto):
    loguear_como(client, "RAYPAC")
    client.post("/raypac/new", data=datos_ingreso(numero_serie, modelo_maquina="OTRA", modelo_otra=texto))
    assert ingreso(numero_serie) is None


@necesita_db
def test_modelo_normal_no_cambia(client, numero_serie):
    loguear_como(client, "RAYPAC")
    client.post("/raypac/new", data=datos_ingreso(numero_serie, modelo_otra="ESTO SE IGNORA"))
    fila = ingreso(numero_serie)
    assert (fila['modelo_maquina'], fila['tipo_maquina']) == ("ITA10", "A BATERIA")


@necesita_db
@pytest.mark.parametrize("modelo, otra, muestra_tipo", [("OTRA", "CARGADOR", False), ("ITA10", "", True)])
def test_vista_del_ingreso_oculta_el_tipo_si_es_otra(client, numero_serie, modelo, otra, muestra_tipo):
    loguear_como(client, "RAYPAC")
    client.post("/raypac/new", data=datos_ingreso(numero_serie, modelo_maquina=modelo, modelo_otra=otra))
    html = client.get(f"/raypac/{ingreso(numero_serie)['id']}").get_data(as_text=True)
    assert ("Tipo Máquina:" in html) is muestra_tipo


@necesita_db
def test_editar_ingreso_otra_muestra_lo_que_se_envia(client, numero_serie):
    loguear_como(client, "RAYPAC")
    client.post("/raypac/new", data=datos_ingreso(numero_serie, modelo_maquina="OTRA", modelo_otra="Batería"))
    html = client.get(f"/raypac/{ingreso(numero_serie)['id']}/edit").get_data(as_text=True)
    assert '<option value="OTRA" selected>' in html
    assert 'value="BATERÍA"' in html


@necesita_db
@pytest.mark.parametrize("modelo, otra, esperado", [("OTRA", "CARGADOR", "NO APLICA"), ("ITA10", "", "BUENO")])
def test_ticket_arranca_en_no_aplica_si_es_otra(client, numero_serie, modelo, otra, esperado):
    loguear_como(client, "RAYPAC")
    client.post("/raypac/new", data=datos_ingreso(numero_serie, modelo_maquina=modelo, modelo_otra=otra))
    raypac_id = ingreso(numero_serie)['id']
    with app.app_context():  # el ticket se crea con el ingreso freezado y recibido en DML
        db = get_db()
        db.execute("UPDATE raypac_entries SET is_frozen = TRUE, estado_envio_equipos = 'RECIBIDO' WHERE id = %s",
                   (raypac_id,))
        db.commit()
    loguear_como(client, "DML_ST")
    html = client.get(f"/tickets/nuevo/{raypac_id}").get_data(as_text=True)
    assert html.count(f'<option value="{esperado}" selected>') == 11  # todas las partes menos OTROS
