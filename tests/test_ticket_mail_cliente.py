# tests/test_ticket_mail_cliente.py - #325: al crear el ticket, mail al cliente con el número
import os
import time

import pytest
from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.blueprints import tickets as tickets_mod
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)

MAIL_CLIENTE = "cliente-qa@example.com"
MAIL_COMERCIAL = "comercial-qa@example.com"


@pytest.fixture
def client():
    """Cliente logueado con un usuario DML_ST temporal; se borra al final."""
    app.config['TESTING'] = True
    email = f"test-ticket-{int(time.time() * 1000)}@qa.local"
    password = "clave-de-prueba-325"
    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "INSERT INTO users (email, password_hash, nombre, role) VALUES (%s, %s, 'QA #325', 'DML_ST') RETURNING id",
            (email, generate_password_hash(password)),
        ).fetchone()['id']
        db.commit()
    with app.test_client() as client:
        client.post('/login', data={'email': email, 'password': password})
        yield client
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM logs_auditoria WHERE id_usuario = %s", (user_id,))
        db.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()


def _crear_ingreso(email_cliente):
    """Ingreso RAYPAC freezado y recibido en DML, sin ticket todavía."""
    serie = f"TEST-TK-{int(time.time() * 1000)}"
    with app.app_context():
        db = get_db()
        correlativo = db.execute(
            "SELECT COALESCE(MAX(numero_correlativo), 0) + 1 AS n FROM raypac_entries"
        ).fetchone()['n']
        raypac_id = db.execute("""
            INSERT INTO raypac_entries
                (numero_correlativo, tipo_solicitud, cliente, numero_serie, modelo_maquina,
                 tipo_maquina, comercial, mail_comercial, email_cliente, fecha_recepcion,
                 is_frozen, numero_remito, estado_envio_equipos)
            VALUES (%s, 'REPARACIÓN', 'Cliente de Prueba QA', %s, 'ITA10',
                    'A BATERIA', 'Comercial QA', %s, %s, CURRENT_DATE,
                    TRUE, '00001-00004321', 'RECIBIDO')
            RETURNING id
        """, (correlativo, serie, MAIL_COMERCIAL, email_cliente)).fetchone()['id']
        db.commit()
    return raypac_id


@pytest.fixture
def ingresos():
    """Fábrica de ingresos de prueba; borra los ingresos y sus tickets al final."""
    creados = []

    def crear(email_cliente=MAIL_CLIENTE):
        creados.append(_crear_ingreso(email_cliente))
        return creados[-1]

    yield crear
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM tickets WHERE raypac_id = ANY(%s)", (creados,))
        db.execute("DELETE FROM raypac_entries WHERE id = ANY(%s)", (creados,))
        db.commit()


@pytest.fixture
def mails(monkeypatch):
    """Captura los mails sin mandarlos. `mails.ok` simula si Resend falla."""
    class Captura(list):
        pass

    enviados = Captura()
    enviados.ok = True
    monkeypatch.setattr(tickets_mod, "send_mail",
                        lambda to, subject, html, **k: enviados.append((to, subject, html)) or enviados.ok)
    return enviados


def _crear_ticket(client, raypac_id):
    return client.post(f"/tickets/nuevo/{raypac_id}",
                       data={"tecnico_responsable": "David"}, follow_redirects=True)


def _ticket(raypac_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM tickets WHERE raypac_id = %s", (raypac_id,)).fetchone()


@necesita_db
def test_crear_ticket_manda_mail_al_cliente_y_al_comercial(client, ingresos, mails):
    raypac_id = ingresos()
    resp = _crear_ticket(client, raypac_id)
    ticket = _ticket(raypac_id)
    assert ticket
    destinatarios = [to for to, _, _ in mails]
    # El comercial sigue recibiendo su mail como antes
    assert MAIL_COMERCIAL in destinatarios
    assert MAIL_CLIENTE in destinatarios
    _, subject, html = next(m for m in mails if m[0] == MAIL_CLIENTE)
    assert ticket['numero_ticket'] in subject
    for dato in (ticket['numero_ticket'], ticket['numero_serie'], "ITA10", "Comercial QA",
                 MAIL_COMERCIAL, "RAYPAC SRL"):
        assert dato in html
    assert "DML" not in html  # texto para el cliente final, sin datos internos de DML
    assert "Se le mandó el número de ticket al cliente" in resp.get_data(as_text=True)


@necesita_db
def test_sin_mail_de_cliente_crea_el_ticket_y_avisa(client, ingresos, mails):
    raypac_id = ingresos(email_cliente=None)
    resp = _crear_ticket(client, raypac_id)
    assert _ticket(raypac_id)
    assert [to for to, _, _ in mails] == [MAIL_COMERCIAL]
    assert "no tiene mail del cliente" in resp.get_data(as_text=True)


@necesita_db
def test_si_falla_el_mail_al_cliente_el_ticket_queda(client, ingresos, mails):
    mails.ok = False
    raypac_id = ingresos()
    resp = _crear_ticket(client, raypac_id)
    assert _ticket(raypac_id)
    assert "No se pudo mandar el mail al cliente" in resp.get_data(as_text=True)
