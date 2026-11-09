# tests/test_stock_ubicacion.py - #309: ubicación física de los repuestos en /stock
import os
import time

import pytest

from CODIGO_FUENTE.app import app  # carga el .env (load_dotenv)
from CODIGO_FUENTE.services.ubicacion_fisica import SIN_UBICACION, normalizar_ubicacion_fisica
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)


# --- Sin base de datos ---------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    # Como aparecen en la planilla de DML (stock al 31/08/2026)
    ("E05-F05-B02", "E05-F05-B02"),
    ("E05 -F04 ", "E05-F04"),
    ("E03-F07-PB -B04", "E03-F07-PB-B04"),
    ("E01 -F04 -PB -B02", "E01-F04-PB-B02"),
    # Escrito a mano: minúscula, espacios, sin ceros, sin guiones
    ("  e5 - f4 - pb - b2 ", "E05-F04-PB-B02"),
    ("e05f05b02", "E05-F05-B02"),
    # Texto que no es un código: se guarda tal cual, en mayúscula y sin espacios de más
    ("uso   taller", "USO TALLER"),
    ("E01 -F0 --P -", "E01-F0--P-"),
    ("E03 -F06 -P -", "E03-F06-P-"),
    ("", SIN_UBICACION),
    ("   ", SIN_UBICACION),
    (None, SIN_UBICACION),
])
def test_normalizar_ubicacion_fisica(entrada, esperado):
    assert normalizar_ubicacion_fisica(entrada) == esperado


# --- Con base de datos ---------------------------------------------------

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def repuesto_test():
    """Crea un repuesto de prueba en el stock de DML y lo borra al final, pase o falle el test."""
    codigo = f"TEST-UBI-{int(time.time() * 1000)}"
    with app.app_context():
        db = get_db()
        numero = db.execute("SELECT MAX(numero) AS max FROM matriz_repuestos").fetchone()['max'] or 0
        db.execute("""
            INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
            VALUES (%s, %s, 'Repuesto de prueba QA', 0, 0, 'RAYPAC')
        """, (numero + 1, codigo))
        db.execute("""
            INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad)
            VALUES (%s, 'DML', 5)
        """, (codigo,))
        db.commit()
    yield codigo
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM stock_ubicaciones WHERE codigo_repuesto = %s", (codigo,))
        db.execute("DELETE FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,))
        db.commit()


def loguear_como(client, role):
    with app.app_context():
        user = get_db().execute("SELECT id FROM users WHERE role = %s ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        pytest.skip(f"No hay usuario con rol {role} en la base")
    with client.session_transaction() as sess:
        sess['user_id'] = user['id']


def ubicacion_guardada(codigo):
    with app.app_context():
        return get_db().execute(
            "SELECT codigo_ubicacion_fisica FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = 'DML'",
            (codigo,)
        ).fetchone()['codigo_ubicacion_fisica']


@necesita_db
@pytest.mark.parametrize("role", ["ADMIN", "DML_ST", "DML_REPUESTOS"])
def test_roles_de_dml_editan_ubicacion_sin_contrasena(client, repuesto_test, role):
    loguear_como(client, role)
    response = client.post(f"/stock/{repuesto_test}/ubicacion-fisica",
                           data={"codigo_ubicacion_fisica": "  e05 -f05   b02 "})
    assert response.status_code == 302
    assert "/stock" in response.headers['Location']
    assert ubicacion_guardada(repuesto_test) == "E05-F05-B02"


@necesita_db
def test_ubicacion_vacia_queda_sin_ubicacion(client, repuesto_test):
    loguear_como(client, "DML_REPUESTOS")
    client.post(f"/stock/{repuesto_test}/ubicacion-fisica", data={"codigo_ubicacion_fisica": "E01-F01"})
    client.post(f"/stock/{repuesto_test}/ubicacion-fisica", data={"codigo_ubicacion_fisica": "   "})
    assert ubicacion_guardada(repuesto_test) == SIN_UBICACION


@necesita_db
def test_raypac_no_puede_editar_ubicacion(client, repuesto_test):
    loguear_como(client, "RAYPAC")
    response = client.post(f"/stock/{repuesto_test}/ubicacion-fisica",
                           data={"codigo_ubicacion_fisica": "E09-F09"})
    assert response.status_code == 302
    assert ubicacion_guardada(repuesto_test) == SIN_UBICACION


@necesita_db
def test_ubicacion_demasiado_larga_no_se_guarda(client, repuesto_test):
    loguear_como(client, "DML_ST")
    client.post(f"/stock/{repuesto_test}/ubicacion-fisica", data={"codigo_ubicacion_fisica": "X" * 101})
    assert ubicacion_guardada(repuesto_test) == SIN_UBICACION


@necesita_db
def test_listado_muestra_columna_filtro_y_busqueda(client, repuesto_test):
    loguear_como(client, "DML_REPUESTOS")

    # Recién creado: aparece en "Sin ubicación" con su botón de editar
    html = client.get(f"/stock?sin_ubicacion=1&buscar={repuesto_test}").get_data(as_text=True)
    assert "<th>Ubicación</th>" in html
    assert f"<strong>{repuesto_test}</strong>" in html
    assert "btn-editar-ubicacion" in html

    # follow_redirects: consume el flash de "actualizada" (que trae el código) para que no ensucie lo que sigue
    html = client.post(f"/stock/{repuesto_test}/ubicacion-fisica", data={"codigo_ubicacion_fisica": "QA-E99-F99"},
                       follow_redirects=True).get_data(as_text=True)
    assert "QA-E99-F99" in html

    # Ya ubicado: sale del filtro "Sin ubicación"...
    html = client.get(f"/stock?sin_ubicacion=1&buscar={repuesto_test}").get_data(as_text=True)
    assert f"<strong>{repuesto_test}</strong>" not in html
    # ...y se encuentra buscando por la ubicación (sin importar mayúsculas)
    html = client.get("/stock?buscar=qa-e99-f99").get_data(as_text=True)
    assert f"<strong>{repuesto_test}</strong>" in html


@necesita_db
def test_raypac_no_ve_la_columna_de_ubicacion(client, repuesto_test):
    loguear_como(client, "RAYPAC")
    html = client.get("/stock").get_data(as_text=True)
    assert "<th>Ubicación</th>" not in html
    assert "btn-editar-ubicacion" not in html


# --- #309 (b): Nuevo y Editar repuesto -----------------------------------

@pytest.fixture
def codigo_nuevo():
    """Código que todavía no existe; se borra al final lo que haya creado el test."""
    codigo = f"TEST-NEW-{int(time.time() * 1000)}"
    yield codigo
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM stock_ubicaciones WHERE codigo_repuesto = %s", (codigo,))
        db.execute("DELETE FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,))
        db.commit()


def ubicacion_de(codigo, ubicacion):
    with app.app_context():
        fila = get_db().execute(
            "SELECT cantidad, codigo_ubicacion_fisica FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
            (codigo, ubicacion)
        ).fetchone()
    return dict(fila) if fila else None


@necesita_db
def test_nuevo_repuesto_muestra_campo_solo_en_dml(client):
    loguear_como(client, "DML_ST")
    assert 'name="codigo_ubicacion_fisica"' in client.get("/stock/new?ubicacion=DML").get_data(as_text=True)
    assert 'name="codigo_ubicacion_fisica"' not in client.get("/stock/new?ubicacion=RAYPAC").get_data(as_text=True)


@necesita_db
def test_nuevo_repuesto_guarda_ubicacion_normalizada(client, codigo_nuevo):
    loguear_como(client, "DML_REPUESTOS")
    response = client.post("/stock/new", data={
        "codigo_repuesto": codigo_nuevo, "item": "Repuesto de prueba QA", "cantidad": "3",
        "codigo_ubicacion_fisica": " e5 - f4 - pb - b2 ",
    })
    assert response.status_code == 302
    assert ubicacion_de(codigo_nuevo, "DML") == {"cantidad": 3, "codigo_ubicacion_fisica": "E05-F04-PB-B02"}


@necesita_db
def test_nuevo_repuesto_sin_ubicacion_queda_pendiente(client, codigo_nuevo):
    loguear_como(client, "DML_REPUESTOS")
    client.post("/stock/new", data={"codigo_repuesto": codigo_nuevo, "item": "Repuesto de prueba QA", "cantidad": "1"})
    assert ubicacion_de(codigo_nuevo, "DML")["codigo_ubicacion_fisica"] == SIN_UBICACION


@necesita_db
def test_nuevo_repuesto_en_raypac_ignora_ubicacion(client, codigo_nuevo):
    loguear_como(client, "DML_ST")
    client.post("/stock/new?ubicacion=RAYPAC", data={
        "codigo_repuesto": codigo_nuevo, "item": "Repuesto de prueba QA", "cantidad": "1",
        "codigo_ubicacion_fisica": "E01-F01",
    })
    assert ubicacion_de(codigo_nuevo, "RAYPAC")["codigo_ubicacion_fisica"] == SIN_UBICACION


@necesita_db
def test_nuevo_repuesto_sin_descripcion_no_rompe(client, codigo_nuevo):
    # Antes este camino renderizaba sin user= y el template tiraba error.
    loguear_como(client, "DML_REPUESTOS")
    response = client.post("/stock/new", data={"codigo_repuesto": codigo_nuevo, "item": "",
                                               "codigo_ubicacion_fisica": "E02-F02"})
    assert response.status_code == 200
    assert 'value="E02-F02"' in response.get_data(as_text=True)  # no se pierde lo que escribió
    assert ubicacion_de(codigo_nuevo, "DML") is None


@necesita_db
def test_editar_repuesto_precarga_y_cambia_ubicacion(client, repuesto_test):
    loguear_como(client, "DML_ST")
    client.post(f"/stock/{repuesto_test}/ubicacion-fisica", data={"codigo_ubicacion_fisica": "E01-F01-B01"})

    html = client.get(f"/stock/{repuesto_test}/edit?ubicacion=DML").get_data(as_text=True)
    assert 'value="E01-F01-B01"' in html

    response = client.post(f"/stock/{repuesto_test}/edit?ubicacion=DML",
                           data={"cantidad": "7", "codigo_ubicacion_fisica": "e3 f7 pb b4"})
    assert response.status_code == 302
    assert ubicacion_de(repuesto_test, "DML") == {"cantidad": 7, "codigo_ubicacion_fisica": "E03-F07-PB-B04"}


@necesita_db
def test_editar_repuesto_sin_ubicacion_no_precarga_el_texto_default(client, repuesto_test):
    loguear_como(client, "DML_ST")
    html = client.get(f"/stock/{repuesto_test}/edit?ubicacion=DML").get_data(as_text=True)
    assert f'value="{SIN_UBICACION}"' not in html
    client.post(f"/stock/{repuesto_test}/edit?ubicacion=DML", data={"cantidad": "5", "codigo_ubicacion_fisica": ""})
    assert ubicacion_de(repuesto_test, "DML")["codigo_ubicacion_fisica"] == SIN_UBICACION


@necesita_db
def test_codigo_con_barra_funciona_en_editar_ubicacion_y_eliminar(client):
    # Con <codigo> en la ruta, "/stock/QA 5/11/edit" daba 404.
    codigo = f"QA {int(time.time() * 1000) % 100000}/11"
    with app.app_context():
        db = get_db()
        numero = db.execute("SELECT MAX(numero) AS max FROM matriz_repuestos").fetchone()['max'] or 0
        db.execute("""INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                      VALUES (%s, %s, 'Repuesto de prueba QA', 0, 0, 'RAYPAC')""", (numero + 1, codigo))
        db.execute("INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad) VALUES (%s, 'DML', 1)", (codigo,))
        db.commit()
    try:
        loguear_como(client, "DML_ST")
        html = client.get("/stock?buscar=" + codigo).get_data(as_text=True)
        assert "/11/edit" in html  # el link de Editar se arma con la barra adentro

        assert client.get(f"/stock/{codigo}/edit?ubicacion=DML").status_code == 200
        assert client.post(f"/stock/{codigo}/edit?ubicacion=DML",
                           data={"cantidad": "2", "codigo_ubicacion_fisica": "E01-F01"}).status_code == 302
        assert client.post(f"/stock/{codigo}/ubicacion-fisica",
                           data={"codigo_ubicacion_fisica": "E02-F02"}).status_code == 302
        assert ubicacion_de(codigo, "DML") == {"cantidad": 2, "codigo_ubicacion_fisica": "E02-F02"}
        assert client.get(f"/api/verificar-stock/{codigo}").status_code == 200

        # Eliminar: la ruta existe (sin contraseña redirige con aviso, no 404)
        loguear_como(client, "ADMIN")
        assert client.post(f"/stock/{codigo}/delete?ubicacion=DML").status_code == 302
    finally:
        with app.app_context():
            db = get_db()
            db.execute("DELETE FROM stock_ubicaciones WHERE codigo_repuesto = %s", (codigo,))
            db.execute("DELETE FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,))
            db.commit()
