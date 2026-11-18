# tests/test_pedidos_envio.py - #342: DML envía el pedido a RAYPAC con remito; RAYPAC confirma la recepción
import os
import random
import time

import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.blueprints import pedidos as pedidos_mod
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)

STOCK_INICIAL = 5


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
def avisos(monkeypatch):
    """Simula los mails (pedido nuevo y pedido enviado) y las alertas de stock bajo: no sale nada real."""
    enviados = {"mails": [], "alertas": []}
    monkeypatch.setattr(pedidos_mod, "send_mail",
                        lambda to, subject, html, **k: enviados["mails"].append((to, subject)) or True)
    monkeypatch.setattr(pedidos_mod, "get_destinatarios", lambda tipo: [f"{tipo.lower()}@dml.test"])
    monkeypatch.setattr(pedidos_mod, "verificar_alerta_stock",
                        lambda codigo, ubicacion="DML", cantidad_anterior=None: enviados["alertas"].append(codigo))
    return enviados


@pytest.fixture
def repuesto():
    """Repuesto de prueba con STOCK_INICIAL en DML (y sin fila en RAYPAC). Se borra al final con sus pedidos."""
    codigo = f"TEST-PED-{int(time.time() * 1000)}"
    with app.app_context():
        db = get_db()
        numero = db.execute("SELECT MAX(numero) AS max FROM matriz_repuestos").fetchone()['max'] or 0
        db.execute("""
            INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
            VALUES (%s, %s, 'Repuesto de prueba QA', 0, 0, 'DML')
        """, (numero + 1, codigo))
        db.execute("INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad) VALUES (%s, 'DML', %s)",
                   (codigo, STOCK_INICIAL))
        db.commit()
    yield codigo
    with app.app_context():
        db = get_db()
        pedidos = [r['pedido_id'] for r in db.execute(
            "SELECT DISTINCT pedido_id FROM pedidos_repuestos_detalles WHERE codigo_repuesto = %s", (codigo,)).fetchall()]
        for pedido_id in pedidos:
            db.execute("DELETE FROM avisos_vistos WHERE tipo IN ('PEDIDO', 'PEDIDO_ENVIADO') AND ref_id = %s", (pedido_id,))
            db.execute("DELETE FROM pedidos_repuestos WHERE id = %s", (pedido_id,))
        db.execute("DELETE FROM stock_ubicaciones WHERE codigo_repuesto = %s", (codigo,))
        db.execute("DELETE FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,))
        db.commit()


@pytest.fixture
def remito():
    """Un remito de prueba que no choque con datos reales (prefijo 99999-)."""
    return f"99999-{random.randint(10_000_000, 99_999_999):08d}"


def pedir(client, codigo, cantidad):
    loguear_como(client, "RAYPAC")
    client.post("/pedidos/new", data={f"qty_{codigo}": str(cantidad)})
    with app.app_context():
        db = get_db()
        pedido = db.execute("""
            SELECT p.id, d.id AS detalle_id FROM pedidos_repuestos p
            JOIN pedidos_repuestos_detalles d ON d.pedido_id = p.id
            WHERE d.codigo_repuesto = %s ORDER BY p.id DESC LIMIT 1
        """, (codigo,)).fetchone()
    return pedido['id'], pedido['detalle_id']


def pedido(pedido_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM pedidos_repuestos WHERE id = %s", (pedido_id,)).fetchone()


def detalle(detalle_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM pedidos_repuestos_detalles WHERE id = %s", (detalle_id,)).fetchone()


def stock(codigo, ubicacion="DML"):
    with app.app_context():
        fila = get_db().execute("SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
                                (codigo, ubicacion)).fetchone()
    return fila['cantidad'] if fila else None


def enviar(client, pedido_id, detalle_id, cantidad, remito, role="DML_REPUESTOS"):
    loguear_como(client, role)
    return client.post(f"/pedidos/{pedido_id}/enviar",
                       data={"numero_remito": remito, f"enviar_{detalle_id}": str(cantidad)})


@necesita_db
def test_envio_descuenta_stock_y_avisa_a_raypac(client, avisos, repuesto, remito):
    pedido_id, detalle_id = pedir(client, repuesto, 3)
    loguear_como(client, "DML_REPUESTOS")
    html = client.get(f"/pedidos/{pedido_id}/enviar").get_data(as_text=True)
    assert f'name="enviar_{detalle_id}"' in html and 'value="3"' in html  # sugiere lo pedido

    enviar(client, pedido_id, detalle_id, 2, remito)  # manda menos de lo pedido
    p = pedido(pedido_id)
    assert (p['estado'], p['numero_remito']) == ("ENVIADO", remito)
    assert p['fecha_envio'] is not None and p['enviado_por'] is not None
    assert detalle(detalle_id)['cantidad_enviada'] == 2
    assert stock(repuesto) == STOCK_INICIAL - 2
    assert avisos["alertas"] == [repuesto]  # pasa por las alertas de stock bajo
    assert any(to == "pedido_enviado@dml.test" for to, _ in avisos["mails"])


@necesita_db
def test_remito_se_completa_con_ceros(client, avisos, repuesto):
    pedido_id, detalle_id = pedir(client, repuesto, 1)
    digitos = str(random.randint(1, 9999))
    with app.app_context():
        if get_db().execute("SELECT 1 FROM pedidos_repuestos WHERE numero_remito = %s",
                            (f"00001-{digitos.zfill(8)}",)).fetchone():
            pytest.skip("Ese remito de prueba ya existe")
    enviar(client, pedido_id, detalle_id, 1, digitos)
    assert pedido(pedido_id)['numero_remito'] == f"00001-{digitos.zfill(8)}"


@necesita_db
@pytest.mark.parametrize("cantidad, remito_valido", [
    (STOCK_INICIAL + 1, True),   # más de lo que hay en DML
    (0, True),                   # no manda nada
    (1, False),                  # sin remito
])
def test_envio_invalido_no_toca_nada(client, avisos, repuesto, remito, cantidad, remito_valido):
    pedido_id, detalle_id = pedir(client, repuesto, 2)
    enviar(client, pedido_id, detalle_id, cantidad, remito if remito_valido else "")
    assert pedido(pedido_id)['estado'] == "PEDIDO"
    assert stock(repuesto) == STOCK_INICIAL


@necesita_db
def test_remito_repetido_en_otro_pedido(client, avisos, repuesto, remito):
    primero, detalle_1 = pedir(client, repuesto, 1)
    enviar(client, primero, detalle_1, 1, remito)
    segundo, detalle_2 = pedir(client, repuesto, 1)
    enviar(client, segundo, detalle_2, 1, remito)
    assert pedido(segundo)['estado'] == "PEDIDO"
    assert stock(repuesto) == STOCK_INICIAL - 1


@necesita_db
def test_recepcion_registra_diferencias_sin_sumar_a_raypac(client, avisos, repuesto, remito):
    pedido_id, detalle_id = pedir(client, repuesto, 3)
    enviar(client, pedido_id, detalle_id, 3, remito)

    loguear_como(client, "RAYPAC")
    html = client.get(f"/pedidos/{pedido_id}").get_data(as_text=True)
    assert f'name="recibido_{detalle_id}"' in html
    client.post(f"/pedidos/{pedido_id}/recibir", data={f"recibido_{detalle_id}": "2"})

    p = pedido(pedido_id)
    assert p['estado'] == "RECIBIDO" and p['fecha_recepcion'] is not None
    assert detalle(detalle_id)['cantidad_recibida'] == 2
    assert stock(repuesto, "RAYPAC") is None          # no se suma al stock de RAYPAC
    assert stock(repuesto) == STOCK_INICIAL - 3       # DML ya descontó al enviar, la recepción no lo toca

    loguear_como(client, "DML_REPUESTOS")
    assert "Diferencia con lo enviado" in client.get(f"/pedidos/{pedido_id}").get_data(as_text=True)


def avisos_de(client):
    return client.get("/api/avisos").get_json()["avisos"]


@necesita_db
def test_campanita_de_raypac_con_lo_que_envio_dml(client, avisos, repuesto, remito):
    pedido_id, detalle_id = pedir(client, repuesto, 2)
    loguear_como(client, "RAYPAC")
    assert not any(a["tipo"] == "PEDIDO_ENVIADO" and a["id"] == pedido_id for a in avisos_de(client))
    html = client.get("/pedidos").get_data(as_text=True)
    assert 'id="avisos-campana"' in html and "Novedades de DML" in html

    enviar(client, pedido_id, detalle_id, 2, remito)
    loguear_como(client, "RAYPAC")
    aviso = next(a for a in avisos_de(client) if a["tipo"] == "PEDIDO_ENVIADO" and a["id"] == pedido_id)
    assert remito in aviso["detalle"] and aviso["url"].endswith(f"/pedidos/{pedido_id}")

    client.get(f"/pedidos/{pedido_id}")  # abrirlo lo saca de la campanita
    assert not any(a["tipo"] == "PEDIDO_ENVIADO" and a["id"] == pedido_id for a in avisos_de(client))

    # A DML no le aparece lo que mandó, y su campanita sigue diciendo "de RAYPAC"
    loguear_como(client, "DML_REPUESTOS")
    assert not any(a["tipo"] == "PEDIDO_ENVIADO" for a in avisos_de(client))
    assert "Novedades de RAYPAC" in client.get("/pedidos").get_data(as_text=True)


@necesita_db
def test_permisos(client, avisos, repuesto, remito):
    pedido_id, detalle_id = pedir(client, repuesto, 1)
    enviar(client, pedido_id, detalle_id, 1, remito, role="RAYPAC")  # RAYPAC no envía
    assert pedido(pedido_id)['estado'] == "PEDIDO"

    enviar(client, pedido_id, detalle_id, 1, remito)
    loguear_como(client, "DML_REPUESTOS")  # Repuestos no confirma la recepción
    client.post(f"/pedidos/{pedido_id}/recibir", data={f"recibido_{detalle_id}": "1"})
    assert pedido(pedido_id)['estado'] == "ENVIADO"

    loguear_como(client, "RAYPAC")  # y ya enviado, RAYPAC no lo puede editar ni cancelar
    client.post(f"/pedidos/{pedido_id}/cancelar")
    assert pedido(pedido_id)['estado'] == "ENVIADO"
