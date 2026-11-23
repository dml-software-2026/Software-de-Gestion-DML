# tests/test_csrf.py - #380: protección CSRF en los formularios y fetch
import glob
import os
import re

import pytest

from CODIGO_FUENTE.app import app
from CODIGO_FUENTE.config import BASE_DIR
from CODIGO_FUENTE.extensions import get_db

necesita_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Falta DATABASE_URL en el entorno"
)

_FORM = re.compile(r'<form\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*>', re.IGNORECASE)
_POST = re.compile(r'method\s*=\s*["\']post["\']', re.IGNORECASE)
_TOKEN = '<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">'


def test_todos_los_formularios_post_tienen_token():
    """Si alguien agrega un <form method="POST"> y se olvida del token, ese
    formulario deja de andar: este test lo frena antes de mergear."""
    sin_token = []
    for ruta in glob.glob(os.path.join(BASE_DIR, "INTERFAZ", "templates", "*.html")):
        with open(ruta, encoding="utf-8") as f:
            html = f.read()
        for m in _FORM.finditer(html):
            if _POST.search(m.group(0)) and _TOKEN not in html[m.end():m.end() + 200]:
                linea = html.count("\n", 0, m.start()) + 1
                sin_token.append(f"{os.path.basename(ruta)}:{linea}")
    assert not sin_token, "Formularios POST sin {{ csrf_token() }}: " + ", ".join(sin_token)


@pytest.fixture
def client(monkeypatch):
    """Cliente con la protección CSRF activada (conftest.py la apaga para el resto)."""
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def token_de(html):
    m = re.search(r'name="csrf-token" content="([^"]+)"', html) or \
        re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "La página no trae el token"
    return m.group(1)


def loguear_como(client, role):
    with app.app_context():
        user = get_db().execute("SELECT id FROM users WHERE role = %s ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        pytest.skip(f"No hay usuario con rol {role} en la base")
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]


@necesita_db
def test_login_sin_token_se_rechaza_y_con_token_entra(client):
    r = client.post("/login", data={"email": "x@x", "password": "x"},
                    headers={"Referer": "http://evil.example/ataque"})
    # Rechazado: vuelve al inicio del propio sistema (no a la página de otro sitio)
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]
    assert "quedó vieja" in client.get("/login").get_data(as_text=True)

    token = token_de(client.get("/login").get_data(as_text=True))
    r = client.post("/login", data={"email": "nadie@dml.test", "password": "x", "csrf_token": token})
    assert r.status_code == 200 and "Credenciales inválidas" in r.get_data(as_text=True)


@necesita_db
def test_post_con_sesion_pero_sin_token_no_hace_nada(client):
    """El caso que frena CSRF: la sesión está abierta pero el POST no trae el token."""
    loguear_como(client, "ADMIN")
    email = "csrf-380@dml.test"
    try:
        r = client.post("/admin/usuarios/nueva",
                        data={"email": email, "password": "atacante1", "role": "ADMIN"})
        assert r.status_code == 302
        with app.app_context():
            assert get_db().execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone() is None
    finally:
        with app.app_context():
            db = get_db()
            db.execute("DELETE FROM users WHERE email = %s", (email,))
            db.commit()


@necesita_db
def test_fetch_del_pago_con_y_sin_token(client):
    """#372: el pago de Entregadas se guarda por fetch con el header X-CSRFToken."""
    with app.app_context():
        ficha = get_db().execute(
            "SELECT id, pago_raypac FROM dml_fichas WHERE is_closed = TRUE ORDER BY id DESC LIMIT 1").fetchone()
    if not ficha:
        pytest.skip("No hay fichas cerradas en la base")
    loguear_como(client, "ADMIN")
    otro = "PAGADO" if ficha["pago_raypac"] == "DEBE" else "DEBE"
    datos = {"campo": "pago_raypac", "valor": otro}
    try:
        r = client.post(f"/dml/{ficha['id']}/pago", data=datos, headers={"Accept": "application/json"})
        assert r.status_code == 400 and not r.get_json()["ok"] and "quedó vieja" in r.get_json()["error"]

        token = token_de(client.get("/dml/entregadas").get_data(as_text=True))
        r = client.post(f"/dml/{ficha['id']}/pago", data=datos,
                        headers={"Accept": "application/json", "X-CSRFToken": token})
        assert r.status_code == 200 and r.get_json()["ok"]
    finally:
        with app.app_context():
            db = get_db()
            db.execute("UPDATE dml_fichas SET pago_raypac = %s WHERE id = %s", (ficha["pago_raypac"], ficha["id"]))
            db.commit()


def test_backup_automatico_no_pide_token(client, monkeypatch):
    """Lo llama el GitHub Actions del backup semanal: tiene su propia clave, no token CSRF.
    Sin la clave correcta tiene que dar 403 (su propio control), no el rechazo de CSRF."""
    monkeypatch.setitem(app.config, "BACKUP_AUTO_TOKEN", "clave-de-prueba")
    r = client.post("/admin/backup/auto", headers={"X-Backup-Token": "otra-cosa"})
    assert r.status_code == 403 and r.get_json() == {"ok": False, "error": "No autorizado"}
