# tests/test_crear_ficha.py - #328: "Crear Ficha" crea la ficha y va directo a la edición
import os
import time

import pytest
from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


@pytest.fixture
def client():
    """Cliente logueado con un usuario DML_ST temporal; se borra al final."""
    app.config['TESTING'] = True
    email = f"test-ficha-{int(time.time() * 1000)}@qa.local"
    password = "clave-de-prueba-328"
    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "INSERT INTO users (email, password_hash, nombre, role) VALUES (%s, %s, 'QA #328', 'DML_ST') RETURNING id",
            (email, generate_password_hash(password)),
        ).fetchone()['id']
        db.commit()
    with app.test_client() as client:
        client.post('/login', data={'email': email, 'password': password})
        yield client
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM logs_auditoria WHERE id_usuario = %s", (user_id,))
        db.execute("DELETE FROM dml_fichas_historial WHERE usuario_id = %s", (user_id,))
        db.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()


@pytest.fixture
def ingreso_con_ticket():
    """Ingreso RAYPAC recibido en DML con su ticket (inspección visual cargada).
    Devuelve (raypac_id, ticket_id). Borra todo lo creado al final."""
    serie = f"TEST-FICHA-{int(time.time() * 1000)}"
    with app.app_context():
        db = get_db()
        correlativo = db.execute(
            "SELECT COALESCE(MAX(numero_correlativo), 0) + 1 AS n FROM raypac_entries"
        ).fetchone()['n']
        raypac_id = db.execute("""
            INSERT INTO raypac_entries
                (numero_correlativo, tipo_solicitud, cliente, numero_serie, modelo_maquina,
                 tipo_maquina, comercial, mail_comercial, fecha_recepcion,
                 is_frozen, numero_remito, estado_envio_equipos)
            VALUES (%s, 'REPARACIÓN', 'Cliente de Prueba QA', %s, 'ITA10',
                    'A BATERIA', 'Comercial QA', 'qa@example.com', CURRENT_DATE,
                    TRUE, '00001-00004321', 'RECIBIDO')
            RETURNING id
        """, (correlativo, serie)).fetchone()['id']
        ticket_id = db.execute("""
            INSERT INTO tickets (numero_ticket, raypac_id, numero_serie, estado, fecha_ingreso,
                                 tecnico_responsable, carcaza, otros)
            VALUES (%s, %s, %s, 'ACTIVO', CURRENT_DATE, 'David', 'ROTO', 'Le falta la tapa')
            RETURNING id
        """, (f"TK-{serie}", raypac_id, serie)).fetchone()['id']
        db.commit()
    yield raypac_id, ticket_id
    with app.app_context():
        db = get_db()
        fichas = [r['id'] for r in db.execute(
            "SELECT id FROM dml_fichas WHERE raypac_id = %s", (raypac_id,)).fetchall()]
        db.execute("UPDATE tickets SET ficha_id = NULL WHERE id = %s", (ticket_id,))
        if fichas:
            db.execute("DELETE FROM dml_partes WHERE ficha_id = ANY(%s)", (fichas,))
            db.execute("DELETE FROM dml_fichas_historial WHERE ficha_id = ANY(%s)", (fichas,))
            db.execute("DELETE FROM dml_fichas WHERE id = ANY(%s)", (fichas,))
        db.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
        db.execute("DELETE FROM raypac_entries WHERE id = %s", (raypac_id,))
        db.commit()


def _fichas(raypac_id):
    with app.app_context():
        return get_db().execute(
            "SELECT * FROM dml_fichas WHERE raypac_id = %s", (raypac_id,)).fetchall()


@necesita_db
def test_get_no_crea_ficha(client, ingreso_con_ticket):
    raypac_id, _ = ingreso_con_ticket
    resp = client.get(f"/dml/new/{raypac_id}")
    assert resp.status_code == 302
    assert f"/raypac/{raypac_id}" in resp.headers['Location']
    assert _fichas(raypac_id) == []


@necesita_db
def test_crear_ficha_va_directo_a_la_edicion(client, ingreso_con_ticket):
    raypac_id, ticket_id = ingreso_con_ticket
    resp = client.post(f"/dml/new/{raypac_id}")
    fichas = _fichas(raypac_id)
    assert len(fichas) == 1
    ficha = fichas[0]
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith(f"/dml/{ficha['id']}/edit")
    assert ficha['tecnico'] == 'David'
    assert ficha['tecnico_resp'] == 'David'
    assert ficha['ticket_id'] == ticket_id
    assert ficha['fecha_ingreso'] is not None
    with app.app_context():
        db = get_db()
        partes = {p['nombre_parte']: p['estado'] for p in db.execute(
            "SELECT nombre_parte, estado FROM dml_partes WHERE ficha_id = %s", (ficha['id'],)).fetchall()}
        ticket = db.execute("SELECT ficha_id FROM tickets WHERE id = %s", (ticket_id,)).fetchone()
    assert len(partes) == 12
    assert partes['CARCAZA'] == 'ROTO'          # viene de la inspección del ticket
    assert partes['OTROS'] == 'Le falta la tapa'
    assert ticket['ficha_id'] == ficha['id']


@necesita_db
def test_segundo_clic_no_duplica_la_ficha(client, ingreso_con_ticket):
    raypac_id, _ = ingreso_con_ticket
    client.post(f"/dml/new/{raypac_id}")
    resp = client.post(f"/dml/new/{raypac_id}")
    fichas = _fichas(raypac_id)
    assert len(fichas) == 1
    assert resp.headers['Location'].endswith(f"/dml/{fichas[0]['id']}/edit")


@necesita_db
def test_edicion_guarda_los_campos_de_abajo_de_repuestos(client, ingreso_con_ticket):
    """Diagnóstico y ciclos quedan fuera del <form> (form="form_ficha") pero
    tienen que seguir viajando al guardar."""
    raypac_id, _ = ingreso_con_ticket
    client.post(f"/dml/new/{raypac_id}")
    ficha_id = _fichas(raypac_id)[0]['id']
    html = client.get(f"/dml/{ficha_id}/edit").get_data(as_text=True)
    assert 'id="form_ficha"' in html
    assert 'form="form_ficha" class="form-control" name="diagnostico_reparacion"' in html
    # Orden pedido por el cliente
    orden = ["DATOS BÁSICOS", "RESPONSABLE Y ESTADO", "ESTADO DEL EQUIPO", "OBSERVACIONES",
             "Repuestos Utilizados", "DIAGNÓSTICO DE REPARACIÓN", "CICLOS Y MANO DE OBRA"]
    posiciones = [html.index(t) for t in orden]
    assert posiciones == sorted(posiciones)
