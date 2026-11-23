# tests/test_contrasenas.py - #375: RAYPAC cambia su contraseña; ADMIN ve la que acaba de poner
import os
import uuid

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

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


def loguear(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


def hash_de(email):
    with app.app_context():
        fila = get_db().execute("SELECT password_hash FROM users WHERE email = %s", (email,)).fetchone()
    return fila['password_hash'] if fila else None


def borrar_usuario(email):
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM logs_auditoria WHERE id_usuario IN (SELECT id FROM users WHERE email = %s)", (email,))
        db.execute("DELETE FROM users WHERE email = %s", (email,))
        db.commit()


@pytest.fixture
def usuario_de_prueba():
    """Crea usuarios descartables (no se toca la contraseña de los usuarios semilla)."""
    creados = []

    def crear(role, password="vieja123"):
        email = f"test-375-{uuid.uuid4().hex[:8]}@dml.test"
        with app.app_context():
            db = get_db()
            user_id = db.execute(
                "INSERT INTO users (email, password_hash, nombre, role, is_active) "
                "VALUES (%s, %s, 'Prueba #375', %s, TRUE) RETURNING id",
                (email, generate_password_hash(password), role)).fetchone()['id']
            db.commit()
        creados.append(email)
        return user_id, email

    yield crear
    for email in creados:
        borrar_usuario(email)


@pytest.fixture
def admin_id():
    with app.app_context():
        fila = get_db().execute("SELECT id FROM users WHERE role = 'ADMIN' ORDER BY id LIMIT 1").fetchone()
    if not fila:
        pytest.skip("No hay usuario ADMIN en la base")
    return fila['id']


@necesita_db
def test_raypac_cambia_su_contrasena(client, usuario_de_prueba):
    user_id, email = usuario_de_prueba("RAYPAC")
    loguear(client, user_id)
    assert "Cambiar mi contraseña" in client.get("/").get_data(as_text=True)  # está en el menú

    r = client.post("/mi-contrasena", data={"actual": "vieja123", "nueva": " nueva456 ", "repetir": "nueva456"})
    assert r.status_code == 302
    assert check_password_hash(hash_de(email), "nueva456")

    # y entra con la nueva
    client.get("/logout")
    r = client.post("/login", data={"email": email, "password": "nueva456"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/")


@necesita_db
@pytest.mark.parametrize("datos", [
    {"actual": "otra-cosa", "nueva": "nueva456", "repetir": "nueva456"},  # actual incorrecta
    {"actual": "vieja123", "nueva": "corta", "repetir": "corta"},         # menos de 6
    {"actual": "vieja123", "nueva": "nueva456", "repetir": "nueva789"},   # no coinciden
    {"actual": "vieja123", "nueva": "vieja123", "repetir": "vieja123"},   # igual a la actual
])
def test_cambio_invalido_no_cambia_nada(client, usuario_de_prueba, datos):
    user_id, email = usuario_de_prueba("RAYPAC")
    loguear(client, user_id)
    antes = hash_de(email)
    r = client.post("/mi-contrasena", data=datos)
    assert r.status_code == 200
    assert hash_de(email) == antes


@necesita_db
@pytest.mark.parametrize("role", ["ADMIN", "DML_ST", "DML_REPUESTOS"])
def test_solo_raypac_cambia_la_suya(client, usuario_de_prueba, role):
    user_id, email = usuario_de_prueba(role)
    loguear(client, user_id)
    assert "Cambiar mi contraseña" not in client.get("/").get_data(as_text=True)
    assert client.get("/mi-contrasena").status_code == 302
    antes = hash_de(email)
    client.post("/mi-contrasena", data={"actual": "vieja123", "nueva": "nueva456", "repetir": "nueva456"})
    assert hash_de(email) == antes


@necesita_db
def test_admin_ve_la_contrasena_al_crear_y_al_cambiarla(client, admin_id):
    email = f"test-375-{uuid.uuid4().hex[:8]}@dml.test"
    try:
        loguear(client, admin_id)
        r = client.post("/admin/usuarios/nueva",
                        data={"email": email, "password": "inicial123", "nombre": "Prueba", "role": "RAYPAC"})
        html = r.get_data(as_text=True)
        assert r.status_code == 200 and 'value="inicial123"' in html and "no se vuelve a mostrar" in html
        assert r.headers["Cache-Control"] == "no-store"
        assert check_password_hash(hash_de(email), "inicial123")

        with app.app_context():
            user_id = get_db().execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()['id']
        r = client.post(f"/admin/usuarios/{user_id}/edit", data={"role": "RAYPAC", "nombre": "Prueba", "password": "reseteada456"})
        assert r.status_code == 200 and 'value="reseteada456"' in r.get_data(as_text=True)
        assert check_password_hash(hash_de(email), "reseteada456")

        # Sin contraseña nueva: guarda el rol y vuelve al listado, sin mostrar nada
        r = client.post(f"/admin/usuarios/{user_id}/edit", data={"role": "RAYPAC", "nombre": "Prueba", "password": ""})
        assert r.status_code == 302

        # Menos de 6 caracteres: no se cambia
        client.post(f"/admin/usuarios/{user_id}/edit", data={"role": "RAYPAC", "nombre": "Prueba", "password": "abc"})
        assert check_password_hash(hash_de(email), "reseteada456")
    finally:
        borrar_usuario(email)


@necesita_db
def test_admin_no_crea_usuario_con_contrasena_corta(client, admin_id):
    email = f"test-375-{uuid.uuid4().hex[:8]}@dml.test"
    try:
        loguear(client, admin_id)
        client.post("/admin/usuarios/nueva", data={"email": email, "password": "abc", "nombre": "Prueba", "role": "RAYPAC"})
        assert hash_de(email) is None
    finally:
        borrar_usuario(email)
