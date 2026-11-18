# tests/test_backup_auto.py - #311: backup semanal automático por mail
import io
import json
import os
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services import backup_auto

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)

TOKEN = "token-de-prueba-311"


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def con_token():
    """Token configurado solo durante el test; el registro de la última corrida se restaura al final."""
    anterior_token = app.config.get("BACKUP_AUTO_TOKEN")
    app.config["BACKUP_AUTO_TOKEN"] = TOKEN
    with app.app_context():
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS app_meta (clave TEXT PRIMARY KEY, valor TEXT)")
        fila = db.execute("SELECT valor FROM app_meta WHERE clave = %s", (backup_auto.CLAVE_ULTIMO,)).fetchone()
        db.commit()
    yield
    app.config["BACKUP_AUTO_TOKEN"] = anterior_token
    with app.app_context():
        db = get_db()
        if fila:
            db.execute("UPDATE app_meta SET valor = %s WHERE clave = %s", (fila["valor"], backup_auto.CLAVE_ULTIMO))
        else:
            db.execute("DELETE FROM app_meta WHERE clave = %s", (backup_auto.CLAVE_ULTIMO,))
        db.commit()


@pytest.fixture
def mails(monkeypatch):
    """Simula el envío: no sale ningún mail real. Devuelve la lista de mails 'enviados'."""
    enviados = []

    def send_mail_falso(to, subject, html, attachments=None, cc=None):
        enviados.append({"to": to, "subject": subject, "attachments": attachments})
        return True

    monkeypatch.setattr(backup_auto, "send_mail", send_mail_falso)
    monkeypatch.setattr(backup_auto, "get_destinatarios", lambda tipo: ["backup@dml.test"] if tipo == "BACKUP" else [])
    return enviados


def pedir_backup(client, token=TOKEN):
    headers = {"X-Backup-Token": token} if token is not None else {}
    return client.post("/admin/backup/auto", headers=headers)


def loguear_admin(client):
    with app.app_context():
        user = get_db().execute("SELECT id FROM users WHERE role = 'ADMIN' ORDER BY id LIMIT 1").fetchone()
    if not user:
        pytest.skip("No hay usuario ADMIN en la base")
    with client.session_transaction() as sess:
        sess['user_id'] = user['id']


# --- Sin base de datos ---------------------------------------------------

def test_sin_token_configurado_no_hace_nada(client, monkeypatch):
    monkeypatch.setitem(app.config, "BACKUP_AUTO_TOKEN", None)
    assert pedir_backup(client).status_code == 403


@pytest.mark.parametrize("token", [None, "", "otro-token"])
def test_token_incorrecto_no_hace_nada(client, monkeypatch, token):
    monkeypatch.setitem(app.config, "BACKUP_AUTO_TOKEN", TOKEN)
    assert pedir_backup(client, token).status_code == 403


def test_get_no_dispara_el_backup(client, monkeypatch):
    monkeypatch.setitem(app.config, "BACKUP_AUTO_TOKEN", TOKEN)
    assert client.get("/admin/backup/auto", headers={"X-Backup-Token": TOKEN}).status_code == 405


# --- Con base de datos ---------------------------------------------------

@necesita_db
def test_manda_el_backup_completo_por_mail(client, con_token, mails):
    respuesta = pedir_backup(client)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["ok"] is True

    assert len(mails) == 1
    assert mails[0]["to"] == ["backup@dml.test"]
    nombre, contenido = mails[0]["attachments"][0]
    assert nombre.startswith("backup_dml_") and nombre.endswith(".zip")
    archivos = zipfile.ZipFile(io.BytesIO(contenido)).namelist()
    assert "backup.sql" in archivos and "csv/users.csv" in archivos

    with app.app_context():
        ultimo = backup_auto.ultimo_backup_automatico(get_db())
    assert ultimo["ok"] is True and ultimo["atrasado"] is False and "backup@dml.test" in ultimo["detalle"]


@necesita_db
def test_sin_destinatarios_falla_y_queda_registrado(client, con_token, mails, monkeypatch):
    monkeypatch.setattr(backup_auto, "get_destinatarios", lambda tipo: [])
    respuesta = pedir_backup(client)
    assert respuesta.status_code == 500
    assert mails == []
    with app.app_context():
        ultimo = backup_auto.ultimo_backup_automatico(get_db())
    assert ultimo["ok"] is False and "destinatarios" in ultimo["detalle"]


@necesita_db
def test_si_el_mail_no_sale_falla(client, con_token, mails, monkeypatch):
    monkeypatch.setattr(backup_auto, "send_mail", lambda *a, **k: False)
    assert pedir_backup(client).status_code == 500
    with app.app_context():
        assert backup_auto.ultimo_backup_automatico(get_db())["ok"] is False


@necesita_db
def test_pantalla_de_backup_muestra_el_ultimo_automatico(client, con_token, mails):
    pedir_backup(client)
    loguear_admin(client)
    html = client.get("/admin/backup").get_data(as_text=True)
    assert "Último backup automático" in html


@necesita_db
def test_pantalla_avisa_si_hace_mas_de_una_semana_que_no_corre(client, con_token):
    hace_10_dias = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO app_meta (clave, valor) VALUES (%s, %s)
               ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor""",
            (backup_auto.CLAVE_ULTIMO, json.dumps({"fecha": hace_10_dias, "ok": True, "detalle": "x"})),
        )
        db.commit()
    loguear_admin(client)
    html = client.get("/admin/backup").get_data(as_text=True)
    assert "Hace más de una semana que no corre" in html
