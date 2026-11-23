# tests/conftest.py - configuración común de pytest
from CODIGO_FUENTE.app import app

# #380: los tests mandan formularios armados a mano, sin el token CSRF de la
# página. Se desactiva para todos; tests/test_csrf.py lo vuelve a activar
# para probar la protección en sí.
app.config["WTF_CSRF_ENABLED"] = False
