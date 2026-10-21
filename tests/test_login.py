# tests/test_login.py
import os
import pytest
from CODIGO_FUENTE.app import app

TEST_USER_EMAIL = os.getenv('TEST_USER_EMAIL')
TEST_USER_PASSWORD = os.getenv('TEST_USER_PASSWORD')

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.mark.skipif(
    not TEST_USER_EMAIL or not TEST_USER_PASSWORD,
    reason="Faltan TEST_USER_EMAIL / TEST_USER_PASSWORD en el entorno"
)
def test_login_exitoso_redirige_a_home(client):
    response = client.post('/login', data={
        'email': TEST_USER_EMAIL,
        'password': TEST_USER_PASSWORD
    })
    assert response.status_code == 302