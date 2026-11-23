# tests/test_remito_freeze.py - #305: el remito se vuelve a cargar a mano al freezar
import os
import time

import pytest

from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.blueprints.raypac import codigos_desfreeze
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.remito import normalizar_remito, numero_para_input



# --- Sin base de datos ---------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    ("4321", "00001-00004321"),
    ("  4321 ", "00001-00004321"),
    ("1", "00001-00000001"),
    ("12345678", "00001-12345678"),
    ("00001-00004321", "00001-00004321"),
    ("0002-00004321", "0002-00004321"),
])
def test_normalizar_remito_valido(entrada, esperado):
    assert normalizar_remito(entrada) == (esperado, None)


@pytest.mark.parametrize("entrada", ["", "   ", None, "123456789", "R-4321", "00001-4321", "43 21"])
def test_normalizar_remito_invalido(entrada):
    remito, error = normalizar_remito(entrada)
    assert remito is None
    assert error


@pytest.mark.parametrize("remito, esperado", [
    ("00001-00004321", "4321"),
    ("00001-12345678", "12345678"),
    ("00001-00000000", "0"),
    ("24000256", ""),   # "remito" = N° de serie (época del #292): no se precarga
    (None, ""),
])
def test_numero_para_input(remito, esperado):
    assert numero_para_input(remito) == esperado


def test_codigo_desfreeze_ultimos_4_del_remito():
    assert "4321" in codigos_desfreeze("00001-00004321")
    # Compatibilidad con el código de antes del #292 (8 dígitos después del guión)
    assert "00004321" in codigos_desfreeze("00001-00004321")
    # Ingresos freezados en la época del #292 (remito = N° de serie)
    assert codigos_desfreeze("24000256") == {"0256"}
    assert codigos_desfreeze("ab12cd") == {"12CD"}
    assert codigos_desfreeze(None) == set()
    assert "1234" not in codigos_desfreeze("00001-00004321")


# --- Con base de datos ---------------------------------------------------

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


@pytest.fixture
def client():
    """Cliente logueado con un usuario ADMIN temporal (no depende de las
    credenciales de cada máquina). El usuario y su auditoría se borran al final."""
    app.config['TESTING'] = True
    email = f"test-remito-{int(time.time() * 1000)}@qa.local"
    password = "clave-de-prueba-305"
    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "INSERT INTO users (email, password_hash, nombre, role) VALUES (%s, %s, 'QA #305', 'ADMIN') RETURNING id",
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


@pytest.fixture
def ingresos_test():
    """Dos ingresos RAYPAC sin freezar; se borran al final, pase o falle el test."""
    serie = f"TEST-REM-{int(time.time() * 1000)}"
    ids = []
    with app.app_context():
        db = get_db()
        for i in (1, 2):
            correlativo = db.execute(
                "SELECT COALESCE(MAX(numero_correlativo), 0) + 1 AS n FROM raypac_entries"
            ).fetchone()['n']
            row = db.execute("""
                INSERT INTO raypac_entries
                    (numero_correlativo, tipo_solicitud, cliente, numero_serie, modelo_maquina,
                     tipo_maquina, comercial, mail_comercial, fecha_recepcion)
                VALUES (%s, 'REPARACIÓN', 'Cliente de Prueba QA', %s, 'ITA10',
                        'A BATERIA', 'Comercial QA', 'qa@example.com', CURRENT_DATE)
                RETURNING id
            """, (correlativo, f"{serie}-{i}")).fetchone()
            ids.append(row['id'])
        db.commit()
    yield ids
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM raypac_entries WHERE id = ANY(%s)", (ids,))
        db.commit()


def _entry(id_):
    with app.app_context():
        return get_db().execute("SELECT * FROM raypac_entries WHERE id = %s", (id_,)).fetchone()


@necesita_db
def test_freezar_sin_remito_no_freeza(client, ingresos_test):
    client.post(f"/raypac/{ingresos_test[0]}/freeze", data={"numero_remito": ""})
    assert not _entry(ingresos_test[0])['is_frozen']


@necesita_db
def test_freezar_con_remito_lo_autocompleta_y_se_puede_repetir(client, ingresos_test):
    for id_ in ingresos_test:
        resp = client.post(f"/raypac/{id_}/freeze", data={"numero_remito": "4321"})
        assert resp.status_code == 302
        entry = _entry(id_)
        assert entry['is_frozen']
        # El remito es el escrito a mano, no el N° de serie, y dos máquinas lo comparten
        assert entry['numero_remito'] == "00001-00004321"
        assert entry['estado_envio_equipos'] == 'ENVIADO'


@necesita_db
def test_desfreezar_con_ultimos_4_del_remito(client, ingresos_test):
    id_ = ingresos_test[0]
    client.post(f"/raypac/{id_}/freeze", data={"numero_remito": "4321"})
    client.post(f"/raypac/{id_}/unfreeze", data={"unfreeze_code": "9999"})
    assert _entry(id_)['is_frozen']
    client.post(f"/raypac/{id_}/unfreeze", data={"unfreeze_code": "4321"})
    assert not _entry(id_)['is_frozen']


# --- #324: aviso por mail a DML al freezar -------------------------------

@pytest.fixture
def mails(monkeypatch):
    """Captura los mails del freezado sin mandarlos. `mails.ok` simula si Resend falla."""
    from CODIGO_FUENTE.blueprints import raypac as raypac_mod

    class Captura(list):
        pass

    enviados = Captura()
    enviados.ok = True
    enviados.destinatarios = ["dml-qa@example.com"]
    monkeypatch.setattr(raypac_mod, "get_destinatarios",
                        lambda tipo: enviados.destinatarios if tipo == "NUEVO_INGRESO" else [])
    monkeypatch.setattr(raypac_mod, "send_mail",
                        lambda to, subject, html, **k: enviados.append((to, subject, html)) or enviados.ok)
    return enviados


@necesita_db
def test_freezar_avisa_por_mail_a_dml(client, ingresos_test, mails):
    id_ = ingresos_test[0]
    resp = client.post(f"/raypac/{id_}/freeze", data={"numero_remito": "4321"}, follow_redirects=True)
    assert len(mails) == 1
    to, subject, html = mails[0]
    assert to == "dml-qa@example.com"
    assert "Cliente de Prueba QA" in subject
    entry = _entry(id_)
    for dato in ("Cliente de Prueba QA", entry["numero_serie"], "ITA10", "00001-00004321", f"/raypac/{id_}"):
        assert dato in html
    assert "No se pudo mandar el aviso" not in resp.get_data(as_text=True)


@necesita_db
def test_freezar_si_falla_el_mail_igual_freeza(client, ingresos_test, mails):
    mails.ok = False
    id_ = ingresos_test[0]
    resp = client.post(f"/raypac/{id_}/freeze", data={"numero_remito": "4321"}, follow_redirects=True)
    assert _entry(id_)["is_frozen"]
    assert "No se pudo mandar el aviso por mail a DML" in resp.get_data(as_text=True)


@necesita_db
def test_freezar_sin_destinatarios_no_manda_ni_avisa(client, ingresos_test, mails):
    mails.destinatarios = []
    id_ = ingresos_test[0]
    resp = client.post(f"/raypac/{id_}/freeze", data={"numero_remito": "4321"}, follow_redirects=True)
    assert _entry(id_)["is_frozen"]
    assert mails == []
    assert "No se pudo mandar el aviso" not in resp.get_data(as_text=True)
