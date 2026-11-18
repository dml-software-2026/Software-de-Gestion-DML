# tests/test_envio_borrador.py - #338: envío de repuestos como borrador sin remito; el remito se pide al freezar
import os
import random

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
def codigo_lista():
    """Un repuesto cualquiera de la lista de RAYPAC, para cargar en el envío."""
    with app.app_context():
        fila = get_db().execute(
            "SELECT codigo_repuesto FROM stock_ubicaciones WHERE ubicacion = 'RAYPAC' ORDER BY codigo_repuesto LIMIT 1"
        ).fetchone()
    if not fila:
        pytest.skip("No hay repuestos en el stock de RAYPAC")
    return fila['codigo_repuesto']


@pytest.fixture
def remitos():
    """Remitos de prueba que no choquen con datos reales (prefijo 99999-). Al final se borra todo lo creado."""
    base = random.randint(10_000_000, 89_999_999)
    numeros = [f"99999-{base + i:08d}" for i in range(3)]
    creados = []
    yield numeros, creados
    with app.app_context():
        db = get_db()
        for envio_id in creados:
            db.execute("DELETE FROM avisos_vistos WHERE tipo = 'REPUESTO' AND ref_id = %s", (envio_id,))
            db.execute("DELETE FROM envios_repuestos WHERE id = %s", (envio_id,))  # renglones en cascada
        db.execute("DELETE FROM raypac_entries WHERE numero_serie LIKE 'TEST-REM-%%'")
        db.commit()


def crear_envio(client, creados, codigo, remito="", cantidad=2):
    with app.app_context():
        antes = get_db().execute("SELECT COALESCE(MAX(id), 0) AS m FROM envios_repuestos").fetchone()['m']
    client.post("/envios/new", data={"tipo_entrega": "REPUESTOS", "numero_remito": remito,
                                     f"qty_{codigo}": str(cantidad)})
    with app.app_context():
        fila = get_db().execute("SELECT * FROM envios_repuestos WHERE id > %s ORDER BY id DESC LIMIT 1",
                                (antes,)).fetchone()
    if fila:
        creados.append(fila['id'])
    return fila


def envio(envio_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM envios_repuestos WHERE id = %s", (envio_id,)).fetchone()


@necesita_db
def test_se_guarda_sin_remito_y_se_ve_como_borrador(client, remitos, codigo_lista):
    _, creados = remitos
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista)
    assert fila is not None
    assert (fila['numero_remito'], fila['estado_envio'], fila['is_frozen']) == (None, 'PREPARACION', False)

    html = client.get(f"/envios/{fila['id']}").get_data(as_text=True)
    assert "Borrador (sin remito)" in html
    assert 'id="freezeModal"' in html
    html = client.get("/envios").get_data(as_text=True)
    assert "Borrador (sin remito)" in html


@necesita_db
def test_borrador_se_edita_y_suma_repuestos_sin_remito(client, remitos, codigo_lista):
    _, creados = remitos
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista)
    # Al abrir Editar el campo del remito viene vacío (no "None", que después no pasa la validación)
    html = client.get(f"/envios/{fila['id']}/edit").get_data(as_text=True)
    assert "None" not in html
    client.post(f"/envios/{fila['id']}/edit", data={"tipo_entrega": "REPUESTOS", "numero_remito": "",
                                                    f"qty_{codigo_lista}": "5"})
    with app.app_context():
        cantidad = get_db().execute("SELECT cantidad FROM envios_repuestos_detalles WHERE envio_id = %s",
                                    (fila['id'],)).fetchone()['cantidad']
    assert cantidad == 5
    assert envio(fila['id'])['numero_remito'] is None


@necesita_db
def test_freezar_sin_remito_no_deja(client, remitos, codigo_lista):
    _, creados = remitos
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista)
    client.post(f"/envios/{fila['id']}/freeze", data={"numero_remito": ""})
    assert envio(fila['id'])['is_frozen'] is False


@necesita_db
def test_freezar_con_remito_lo_completa_y_lo_envia(client, remitos, codigo_lista):
    (remito, *_), creados = remitos
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista)
    client.post(f"/envios/{fila['id']}/freeze", data={"numero_remito": remito})
    final = envio(fila['id'])
    assert (final['is_frozen'], final['estado_envio'], final['numero_remito']) == (True, 'ENVIADO', remito)


@necesita_db
def test_freezar_completa_el_remito_con_ceros(client, remitos, codigo_lista):
    _, creados = remitos
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista)
    digitos = str(random.randint(1, 9999))
    with app.app_context():
        ocupado = get_db().execute("SELECT 1 FROM envios_repuestos WHERE numero_remito = %s",
                                   (f"00001-{digitos.zfill(8)}",)).fetchone()
    if ocupado:
        pytest.skip("Ese remito de prueba ya existe en la base")
    client.post(f"/envios/{fila['id']}/freeze", data={"numero_remito": digitos})
    assert envio(fila['id'])['numero_remito'] == f"00001-{digitos.zfill(8)}"


@necesita_db
def test_freezar_respeta_el_remito_cargado_en_el_alta(client, remitos, codigo_lista):
    (remito, *_), creados = remitos
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista, remito=remito)
    assert fila['numero_remito'] == remito
    client.post(f"/envios/{fila['id']}/freeze", data={})  # sin tocar el campo del modal
    assert envio(fila['id'])['numero_remito'] == remito
    assert envio(fila['id'])['is_frozen'] is True


@necesita_db
def test_remito_repetido_en_otro_envio_no_deja_freezar(client, remitos, codigo_lista):
    (remito, *_), creados = remitos
    loguear_como(client, "RAYPAC")
    crear_envio(client, creados, codigo_lista, remito=remito)
    borrador = crear_envio(client, creados, codigo_lista)
    client.post(f"/envios/{borrador['id']}/freeze", data={"numero_remito": remito})
    assert envio(borrador['id'])['is_frozen'] is False
    assert envio(borrador['id'])['numero_remito'] is None


@necesita_db
def test_remito_compartido_con_una_maquina_se_permite(client, remitos, codigo_lista):
    (_, remito, _), creados = remitos
    with app.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO raypac_entries (numero_correlativo, fecha_recepcion, tipo_solicitud, cliente, numero_serie,
                                        modelo_maquina, tipo_maquina, comercial, mail_comercial, numero_remito)
            VALUES (0, CURRENT_DATE, 'REPARACIÓN', 'Cliente de Prueba QA', 'TEST-REM-1', 'ITA10', 'A BATERIA',
                    'Ezequiel Pacheco', 'ezequiel.pacheco@raypac.net', %s)
        """, (remito,))
        db.commit()
    loguear_como(client, "RAYPAC")
    fila = crear_envio(client, creados, codigo_lista, remito=remito)
    assert fila is not None and fila['numero_remito'] == remito
