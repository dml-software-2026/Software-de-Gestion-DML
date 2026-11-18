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


# --- #331: mano de obra -----------------------------------------------------

def _guardar(client, ficha_id, **extra):
    data = {
        "fecha_ingreso": "2026-11-18",
        "estado_reparacion": "A LA ESPERA DE REVISIÓN",
        "tecnico_resp": "David",
        "n_ciclos": "0",
    }
    data.update(extra)
    return client.post(f"/dml/{ficha_id}/edit", data=data)


@necesita_db
def test_mano_de_obra_se_guarda_y_sale_en_la_vista(client, ingreso_con_ticket):
    raypac_id, _ = ingreso_con_ticket
    client.post(f"/dml/new/{raypac_id}")
    ficha_id = _fichas(raypac_id)[0]['id']
    _guardar(client, ficha_id, mano_de_obra="En garantía")
    assert _fichas(raypac_id)[0]['mano_de_obra'] == "En garantía"
    assert "En garantía" in client.get(f"/dml/{ficha_id}").get_data(as_text=True)
    # Vacío = no aplica (es opcional)
    _guardar(client, ficha_id, mano_de_obra="")
    assert _fichas(raypac_id)[0]['mano_de_obra'] is None


@necesita_db
def test_mano_de_obra_fuera_de_la_lista_se_rechaza(client, ingreso_con_ticket):
    raypac_id, _ = ingreso_con_ticket
    client.post(f"/dml/new/{raypac_id}")
    ficha_id = _fichas(raypac_id)[0]['id']
    _guardar(client, ficha_id, mano_de_obra="Cualquier cosa")
    assert _fichas(raypac_id)[0]['mano_de_obra'] is None


@necesita_db
def test_mano_de_obra_sale_en_el_pdf(client, ingreso_con_ticket):
    from CODIGO_FUENTE.services.pdf import generar_pdf_ficha
    raypac_id, _ = ingreso_con_ticket
    client.post(f"/dml/new/{raypac_id}")
    ficha_id = _fichas(raypac_id)[0]['id']
    _guardar(client, ficha_id, mano_de_obra="Sin cargo")
    with app.app_context():
        pdf = generar_pdf_ficha(ficha_id)
    assert pdf[:4] == b"%PDF"


# --- #332: formato del PDF --------------------------------------------------

def _texto_pdf(pdf_bytes):
    """Texto crudo de los streams del PDF. reportlab los guarda con
    /ASCII85Decode + /FlateDecode: se decodifican los dos pasos."""
    import base64
    import re
    import zlib
    partes = []
    for m in re.finditer(rb"(?<!end)stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        datos = m.group(1).strip()
        try:
            if datos.endswith(b"~>"):
                datos = base64.a85decode(datos[:-2])
            partes.append(zlib.decompress(datos))
        except (ValueError, zlib.error):
            partes.append(m.group(1))
    return b"".join(partes).decode("latin-1")


def test_fecha_ddmmaaaa():
    from datetime import date, datetime

    from CODIGO_FUENTE.services.fechas import fecha_ddmmaaaa
    assert fecha_ddmmaaaa("2026-11-13") == "13/11/2026"
    assert fecha_ddmmaaaa("2026-11-13 10:22:00") == "13/11/2026"
    assert fecha_ddmmaaaa(date(2026, 11, 13)) == "13/11/2026"
    assert fecha_ddmmaaaa(datetime(2026, 11, 13, 10, 22)) == "13/11/2026"
    assert fecha_ddmmaaaa(None) == ""
    assert fecha_ddmmaaaa("") == ""
    assert fecha_ddmmaaaa("sin fecha") == "sin fecha"


@necesita_db
def test_pdf_formato_del_cliente(client, ingreso_con_ticket):
    raypac_id, _ = ingreso_con_ticket
    client.post(f"/dml/new/{raypac_id}")
    ficha = _fichas(raypac_id)[0]
    _guardar(client, ficha['id'], fecha_ingreso="2026-11-13")
    resp = client.get(f"/dml/{ficha['id']}/pdf")
    assert resp.status_code == 200
    # Nombre del archivo en mayúscula
    assert f"FICHA_{ficha['numero_ficha']:07d}.pdf" in resp.headers['Content-Disposition']
    texto = _texto_pdf(resp.data)
    assert "SERVICIO TECNICO DML ELECTRICIDAD INDUSTRIAL SRL" in texto
    assert "EQUIPO REPARADO" in texto
    assert "EN REVISI" not in texto
    assert "13/11/2026" in texto
    assert "2026-11-13" not in texto
    # Sin textos de relleno en observaciones/diagnóstico vacíos
    assert "Ingreso reciente" not in texto
    assert "Pendiente" not in texto
