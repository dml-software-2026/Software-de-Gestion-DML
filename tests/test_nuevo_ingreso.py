# tests/test_crear_ficha.py
import os
import time
import pytest
from CODIGO_FUENTE.app import app
from CODIGO_FUENTE.extensions import get_db

TEST_USER_EMAIL = os.getenv('TEST_USER_EMAIL')
TEST_USER_PASSWORD = os.getenv('TEST_USER_PASSWORD')

pytestmark = pytest.mark.skipif(
    not TEST_USER_EMAIL or not TEST_USER_PASSWORD,
    reason="Faltan TEST_USER_EMAIL / TEST_USER_PASSWORD en el entorno"
)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    client.post('/login', data={
        'email': TEST_USER_EMAIL,
        'password': TEST_USER_PASSWORD
    })
    return client


@pytest.fixture
def ficha_test_data():
    """Genera datos únicos para la ficha y limpia el registro al final, pase o falle el test."""
    numero_serie = f"TEST-{int(time.time())}"
    data = {
        'tipo_solicitud': 'REPARACIÓN',
        'cliente': 'Cliente de Prueba QA',
        'numero_serie': numero_serie,
        'modelo_maquina': 'ITA10',
        'tipo_maquina': 'A BATERIA',
        'comercial': 'Ezequiel Pacheco',
        'mail_comercial': 'ezequiel.pacheco@raypac.net',
    }
    yield data

    # Cleanup: borra el registro de test de la DB, sin importar si el test pasó o falló
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM raypac_entries WHERE numero_serie = %s", (numero_serie,))
        db.commit()


def test_crear_ficha_raypac_exitosa(logged_in_client, ficha_test_data):
    response = logged_in_client.post('/raypac/new', data=ficha_test_data)

    assert response.status_code == 302
    assert '/raypac/' in response.headers['Location']


def test_crear_ficha_raypac_sin_campos_obligatorios(logged_in_client):
    response = logged_in_client.post('/raypac/new', data={
        'tipo_solicitud': '',
        'cliente': '',
    })

    assert response.status_code == 200  # re-renderiza el form, no redirige