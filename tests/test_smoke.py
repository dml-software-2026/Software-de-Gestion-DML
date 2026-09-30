import pytest
from CODIGO_FUENTE.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page_redirige_a_login_sin_sesion(client):
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']