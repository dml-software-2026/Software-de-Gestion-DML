"""#379: límite de intentos de login fallidos por usuario.

Después de MAX_FALLIDOS intentos fallidos dentro de VENTANA para el mismo
email, el login de ese email queda bloqueado hasta que el más viejo de esos
intentos salga de la ventana. Un login correcto limpia la cuenta.

Se guarda en memoria del proceso: alcanza porque gunicorn corre con un solo
worker (Procfile) y un reinicio solo resetea los contadores. Se cuenta por
email (no por IP) porque detrás del proxy de Render la IP real no es
confiable sin más configuración.
"""
import threading
import time

MAX_FALLIDOS = 5
VENTANA = 15 * 60  # segundos

_fallidos = {}
_lock = threading.Lock()


def _clave(email):
    return (email or "").strip().lower()


def _vigentes(clave, ahora):
    intentos = [t for t in _fallidos.get(clave, []) if ahora - t < VENTANA]
    if intentos:
        _fallidos[clave] = intentos
    else:
        _fallidos.pop(clave, None)
    return intentos


def segundos_bloqueado(email, ahora=None):
    """Segundos que faltan para poder volver a intentar (0 = no bloqueado)."""
    ahora = time.time() if ahora is None else ahora
    with _lock:
        intentos = _vigentes(_clave(email), ahora)
        if len(intentos) < MAX_FALLIDOS:
            return 0
        return max(1, int(intentos[0] + VENTANA - ahora))


def registrar_fallido(email, ahora=None):
    ahora = time.time() if ahora is None else ahora
    with _lock:
        clave = _clave(email)
        _vigentes(clave, ahora)
        _fallidos.setdefault(clave, []).append(ahora)


def limpiar(email):
    with _lock:
        _fallidos.pop(_clave(email), None)
