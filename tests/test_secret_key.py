"""#376: en Render la app no arranca sin una SECRET_KEY propia."""
import pytest

from CODIGO_FUENTE.config import DEFAULT_SECRET_KEY, validar_secret_key


@pytest.mark.parametrize("clave", [None, "", DEFAULT_SECRET_KEY])
def test_en_render_sin_clave_propia_no_arranca(clave):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validar_secret_key(clave, en_render=True)


def test_en_render_con_clave_propia_arranca():
    validar_secret_key("a" * 64, en_render=True)


@pytest.mark.parametrize("clave", [None, DEFAULT_SECRET_KEY, "a" * 64])
def test_en_local_cualquier_clave_arranca(clave):
    validar_secret_key(clave, en_render=False)
