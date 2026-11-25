# tests/test_pedidos.py - #341: pedidos de repuestos de RAYPAC a DML
import os

import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.blueprints import pedidos as pedidos_mod
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.avisos import avisos_sin_ver

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def usuario(role):
    with app.app_context():
        user = get_db().execute("SELECT * FROM users WHERE role = %s ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        pytest.skip(f"No hay usuario con rol {role} en la base")
    return user


def loguear_como(client, role):
    user = usuario(role)
    with client.session_transaction() as sess:
        sess['user_id'] = user['id']
    return user


@pytest.fixture
def mails(monkeypatch):
    """Simula el mail a DML: no sale ninguno real."""
    enviados = []
    monkeypatch.setattr(pedidos_mod, "send_mail", lambda to, subject, html, **k: enviados.append((to, subject)) or True)
    monkeypatch.setattr(pedidos_mod, "get_destinatarios",
                        lambda tipo: ["dml@dml.test"] if tipo == "NUEVO_INGRESO" else [])
    return enviados


@pytest.fixture
def repuesto():
    """Un repuesto del stock de DML y su cantidad."""
    with app.app_context():
        fila = get_db().execute(
            "SELECT codigo_repuesto, cantidad FROM stock_ubicaciones WHERE ubicacion = 'DML' ORDER BY codigo_repuesto LIMIT 1"
        ).fetchone()
    if not fila:
        pytest.skip("No hay repuestos en el stock de DML")
    return fila['codigo_repuesto'], fila['cantidad']


@pytest.fixture
def creados():
    """ids de los pedidos que crea el test; se borran al final, pase o falle."""
    ids = []
    yield ids
    with app.app_context():
        db = get_db()
        for pedido_id in ids:
            db.execute("DELETE FROM avisos_vistos WHERE tipo = 'PEDIDO' AND ref_id = %s", (pedido_id,))
            db.execute("DELETE FROM pedidos_repuestos WHERE id = %s", (pedido_id,))  # renglones en cascada
        db.commit()


def crear_pedido(client, creados, codigo, cantidad, observaciones=""):
    with app.app_context():
        antes = get_db().execute("SELECT COALESCE(MAX(id), 0) AS m FROM pedidos_repuestos").fetchone()['m']
    client.post("/pedidos/new", data={f"qty_{codigo}": str(cantidad), "observaciones": observaciones})
    with app.app_context():
        fila = get_db().execute("SELECT * FROM pedidos_repuestos WHERE id > %s ORDER BY id DESC LIMIT 1",
                                (antes,)).fetchone()
    if fila:
        creados.append(fila['id'])
    return fila


def renglones(pedido_id):
    with app.app_context():
        return [tuple(r.values()) for r in get_db().execute(
            "SELECT codigo_repuesto, cantidad FROM pedidos_repuestos_detalles WHERE pedido_id = %s ORDER BY id",
            (pedido_id,)).fetchall()]


def estado(pedido_id):
    with app.app_context():
        return get_db().execute("SELECT estado FROM pedidos_repuestos WHERE id = %s", (pedido_id,)).fetchone()['estado']


@necesita_db
def test_raypac_pide_y_a_dml_le_llega_el_aviso(client, mails, repuesto, creados):
    codigo, _ = repuesto
    raypac = loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, 2, "  urgente   para   el lunes ")
    assert pedido is not None
    assert (pedido['estado'], pedido['observaciones'], pedido['creado_por']) == ("PEDIDO", "urgente para el lunes", raypac['id'])
    assert renglones(pedido['id']) == [(codigo, 2)]

    # Mail a los destinatarios de "Nuevo pedido o máquina ingresada"
    assert len(mails) == 1 and mails[0][0] == "dml@dml.test" and f"#{pedido['id']}" in mails[0][1]

    # Campanita: la ven Repuestos, el técnico (también prepara pedidos) y ADMIN
    with app.app_context():
        assert any(a["tipo"] == "PEDIDO" and a["id"] == pedido['id'] for a in avisos_sin_ver(usuario("DML_REPUESTOS")))
        assert any(a["tipo"] == "PEDIDO" and a["id"] == pedido['id'] for a in avisos_sin_ver(usuario("DML_ST")))

    # Abrirlo lo saca de la campanita de quien lo abrió
    loguear_como(client, "DML_REPUESTOS")
    client.get(f"/pedidos/{pedido['id']}")
    with app.app_context():
        assert not any(a["tipo"] == "PEDIDO" and a["id"] == pedido['id'] for a in avisos_sin_ver(usuario("DML_REPUESTOS")))


@necesita_db
def test_se_puede_pedir_mas_de_lo_que_hay(client, mails, repuesto, creados):
    codigo, hay = repuesto
    loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, hay + 5)
    assert pedido is not None and renglones(pedido['id']) == [(codigo, hay + 5)]


@necesita_db
@pytest.mark.parametrize("cantidad", ["", "0", "-1", "dos", "1.5"])
def test_pedido_vacio_o_invalido_no_se_guarda(client, mails, repuesto, creados, cantidad):
    codigo, _ = repuesto
    loguear_como(client, "RAYPAC")
    assert crear_pedido(client, creados, codigo, cantidad) is None
    assert mails == []


@necesita_db
def test_raypac_corrige_y_cancela_mientras_esta_pedido(client, mails, repuesto, creados):
    codigo, _ = repuesto
    loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, 1)
    client.post(f"/pedidos/{pedido['id']}/edit", data={f"qty_{codigo}": "4", "observaciones": ""})
    assert renglones(pedido['id']) == [(codigo, 4)]
    client.post(f"/pedidos/{pedido['id']}/cancelar")
    assert estado(pedido['id']) == "CANCELADO"


@necesita_db
def test_en_preparacion_raypac_ya_no_lo_cambia(client, mails, repuesto, creados):
    codigo, _ = repuesto
    loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, 1)
    loguear_como(client, "DML_REPUESTOS")
    client.post(f"/pedidos/{pedido['id']}/preparar")
    assert estado(pedido['id']) == "EN_PREPARACION"

    loguear_como(client, "RAYPAC")
    client.post(f"/pedidos/{pedido['id']}/edit", data={f"qty_{codigo}": "9"})
    client.post(f"/pedidos/{pedido['id']}/cancelar")
    assert renglones(pedido['id']) == [(codigo, 1)]
    assert estado(pedido['id']) == "EN_PREPARACION"


@necesita_db
def test_permisos_por_rol(client, mails, repuesto, creados):
    codigo, _ = repuesto
    loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, 1)

    # RAYPAC no lo puede poner en preparación; Repuestos no puede pedir
    client.post(f"/pedidos/{pedido['id']}/preparar")
    assert estado(pedido['id']) == "PEDIDO"
    loguear_como(client, "DML_REPUESTOS")
    assert crear_pedido(client, creados, codigo, 1) is None

    # El técnico prepara pedidos (Ricardo, pedido del cliente 25/11), pero no pide
    loguear_como(client, "DML_ST")
    assert client.get("/pedidos").status_code == 200
    assert client.get(f"/pedidos/{pedido['id']}").status_code == 200
    assert crear_pedido(client, creados, codigo, 1) is None
    client.post(f"/pedidos/{pedido['id']}/preparar")
    assert estado(pedido['id']) == "EN_PREPARACION"


@necesita_db
def test_listado_y_formulario(client, mails, repuesto, creados):
    codigo, _ = repuesto
    loguear_como(client, "RAYPAC")
    html = client.get("/pedidos/new").get_data(as_text=True)
    assert 'id="buscar-repuesto"' in html and 'id="barra-pedido"' in html
    assert f'name="qty_{codigo}"' in html
    assert "codigo_ubicacion_fisica" not in html  # RAYPAC ve cuánto hay, sin ubicación

    pedido = crear_pedido(client, creados, codigo, 1)
    html = client.get("/pedidos").get_data(as_text=True)
    assert f"#{pedido['id']}" in html
    client.post(f"/pedidos/{pedido['id']}/cancelar")
    assert f"#{pedido['id']}</strong>" not in client.get("/pedidos").get_data(as_text=True)
    assert f"#{pedido['id']}</strong>" in client.get("/pedidos?estado=todos").get_data(as_text=True)


@pytest.fixture
def pdf_sin_comprimir(monkeypatch):
    """El PDF sin comprimir, para poder buscar el texto adentro (#374)."""
    from reportlab import rl_config
    monkeypatch.setattr(rl_config, "pageCompression", 0)


@necesita_db
def test_pdf_del_pedido_para_el_deposito(client, mails, repuesto, creados, pdf_sin_comprimir):
    """#374: DML descarga la hoja con qué repuestos, cuántos y su ubicación física."""
    codigo, _ = repuesto
    with app.app_context():
        ubicacion = get_db().execute(
            "SELECT codigo_ubicacion_fisica FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = 'DML'",
            (codigo,)).fetchone()['codigo_ubicacion_fisica']
    loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, 3)

    for role in ("DML_REPUESTOS", "DML_ST", "ADMIN"):
        loguear_como(client, role)
        assert "Descargar PDF" in client.get(f"/pedidos/{pedido['id']}").get_data(as_text=True)
        r = client.get(f"/pedidos/{pedido['id']}/pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
        assert f"PEDIDO_{pedido['id']:07d}.pdf" in r.headers["Content-Disposition"]
        contenido = r.get_data()
        assert contenido.startswith(b"%PDF")
        assert codigo.upper().encode() in contenido and ubicacion.encode() in contenido


@necesita_db
def test_pdf_del_pedido_no_lo_descarga_raypac(client, mails, repuesto, creados):
    """#374: la hoja lleva la ubicación física, que RAYPAC no ve (#308). El PDF es solo de DML."""
    codigo, _ = repuesto
    loguear_como(client, "RAYPAC")
    pedido = crear_pedido(client, creados, codigo, 1)
    assert "Descargar PDF" not in client.get(f"/pedidos/{pedido['id']}").get_data(as_text=True)
    assert client.get(f"/pedidos/{pedido['id']}/pdf").status_code == 302


@necesita_db
def test_pdf_de_un_pedido_que_no_existe(client):
    loguear_como(client, "DML_REPUESTOS")
    r = client.get("/pedidos/999999999/pdf")
    assert r.status_code == 302 and r.headers["Location"].endswith("/pedidos")
