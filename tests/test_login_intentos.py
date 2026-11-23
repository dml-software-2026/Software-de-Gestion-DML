"""#379: límite de intentos de login fallidos por usuario."""
import pytest

from CODIGO_FUENTE.services import login_intentos as li


@pytest.fixture(autouse=True)
def _limpio():
    li._fallidos.clear()
    yield
    li._fallidos.clear()


def test_bloquea_al_llegar_al_maximo():
    for i in range(li.MAX_FALLIDOS - 1):
        li.registrar_fallido("a@x.com", ahora=1000 + i)
    assert li.segundos_bloqueado("a@x.com", ahora=1010) == 0
    li.registrar_fallido("a@x.com", ahora=1010)
    assert li.segundos_bloqueado("a@x.com", ahora=1011) > 0


def test_se_desbloquea_al_salir_de_la_ventana():
    for _ in range(li.MAX_FALLIDOS):
        li.registrar_fallido("a@x.com", ahora=1000)
    assert li.segundos_bloqueado("a@x.com", ahora=1000 + li.VENTANA) == 0


def test_no_distingue_mayusculas_ni_espacios():
    for _ in range(li.MAX_FALLIDOS):
        li.registrar_fallido(" A@X.com ", ahora=1000)
    assert li.segundos_bloqueado("a@x.com", ahora=1001) > 0


def test_otro_usuario_no_se_bloquea():
    for _ in range(li.MAX_FALLIDOS):
        li.registrar_fallido("a@x.com", ahora=1000)
    assert li.segundos_bloqueado("b@x.com", ahora=1001) == 0


def test_login_correcto_limpia():
    for _ in range(li.MAX_FALLIDOS - 1):
        li.registrar_fallido("a@x.com", ahora=1000)
    li.limpiar("a@x.com")
    li.registrar_fallido("a@x.com", ahora=1001)
    assert li.segundos_bloqueado("a@x.com", ahora=1002) == 0
