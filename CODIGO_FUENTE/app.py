import logging
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect

load_dotenv()

from CODIGO_FUENTE.blueprints.admin import admin_bp, backup_auto
from CODIGO_FUENTE.blueprints.api import api_bp
from CODIGO_FUENTE.blueprints.auth import auth_bp
from CODIGO_FUENTE.blueprints.dml import dml_bp
from CODIGO_FUENTE.blueprints.envios import envios_bp
from CODIGO_FUENTE.blueprints.estadisticas import estadisticas_bp
from CODIGO_FUENTE.blueprints.notificaciones import notificaciones_bp
from CODIGO_FUENTE.blueprints.pedidos import pedidos_bp
from CODIGO_FUENTE.blueprints.raypac import raypac_bp
from CODIGO_FUENTE.blueprints.stock import stock_bp
from CODIGO_FUENTE.blueprints.tickets import tickets_bp
from CODIGO_FUENTE.config import (
    BASE_DIR,
    MANO_DE_OBRA_OPCIONES,
    TECNICOS_ST,
    Config,
    validar_secret_key,
)
from CODIGO_FUENTE.decorators import get_current_user_jinja
from CODIGO_FUENTE.extensions import close_db, get_db, init_db, preparar_base
from CODIGO_FUENTE.services.fechas import fecha_ddmmaaaa
from CODIGO_FUENTE.services.stock import get_alert_badge

# Nivel configurable por entorno: en Render se puede setear LOG_LEVEL=DEBUG
# para desarrollo sin tocar código; por defecto INFO en producción.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "INTERFAZ", "templates"),
    static_folder=os.path.join(BASE_DIR, "INTERFAZ", "static"),
    static_url_path="/static"
)
app.config.from_object(Config)
validar_secret_key(app.config["SECRET_KEY"], en_render=bool(os.environ.get("RENDER")))  # #376

logger = logging.getLogger(__name__)

# Hacer funciones de negocio disponibles en todos los templates Jinja2
app.jinja_env.globals.update(
    get_current_user=get_current_user_jinja,
    get_alert_badge=get_alert_badge,
    current_year=lambda: datetime.now().year,
    tecnicos_st=TECNICOS_ST,  # #327
    mano_de_obra_opciones=MANO_DE_OBRA_OPCIONES,  # #331
)
app.jinja_env.filters['fecha'] = fecha_ddmmaaaa  # #332: {{ valor|fecha }} -> dd/mm/aaaa

# Cerrar la conexión a la BD al final de cada request
app.teardown_appcontext(close_db)

# Registrar blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(raypac_bp)
app.register_blueprint(dml_bp)
app.register_blueprint(tickets_bp)
app.register_blueprint(envios_bp)
app.register_blueprint(stock_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(estadisticas_bp)
app.register_blueprint(api_bp)
app.register_blueprint(notificaciones_bp)
app.register_blueprint(pedidos_bp)

# #380: protección CSRF. Todo POST tiene que traer el token de la sesión:
# campo oculto {{ csrf_token() }} en cada <form method="POST"> o header
# X-CSRFToken en los fetch (lo leen de <meta name="csrf-token"> de base.html).
# Así una página de otro sitio no puede mandar formularios con la sesión
# abierta de un usuario. tests/test_csrf.py revisa que ningún form se quede
# sin token.
csrf = CSRFProtect(app)
# La llama el GitHub Actions del backup semanal, no un navegador: tiene su
# propia clave (BACKUP_AUTO_TOKEN) y no puede traer un token de sesión.
csrf.exempt(backup_auto)


@app.errorhandler(CSRFError)
def csrf_vencido(e):
    """#380: token faltante o viejo (ej. la página quedó abierta desde antes
    de cerrar sesión o de un deploy): en vez de un 400 pelado, volver a la
    página con un aviso. Los fetch reciben el mismo mensaje en JSON."""
    logger.warning("CSRF rechazado en %s: %s", request.path, e.description)
    mensaje = "La página quedó vieja y no se guardó nada. Volvé a intentarlo."
    if request.accept_mimetypes.best == "application/json":
        return jsonify(ok=False, error=mensaje + " (Si sigue pasando, recargá la página.)"), 400
    flash(mensaje, "warning")
    # Solo se vuelve a una página del propio sistema: si el POST vino de otro
    # sitio (justo el caso que esto frena), no se redirige para allá.
    anterior = request.referrer
    if not anterior or urlparse(anterior).netloc != request.host:
        anterior = url_for("auth.index")
    return redirect(anterior)


@app.route("/health")
def health():
    try:
        get_db().execute("SELECT 1").fetchone()
        return {"status": "ok"}, 200
    except Exception:
        logger.exception("Health check falló")
        return {"status": "error"}, 500

@app.before_request
def apply_migrations():
    """Aplica migraciones de BD al iniciar la app."""
    if not hasattr(app, '_migrations_applied'):
        # #244: antes acá se decidía entre init_db() y migrate_db() según si
        # existía el archivo dml.db (resto de la era SQLite: en Render nunca
        # existe, así que corría la inicialización completa en cada arranque)
        # y después se volvía a correr el seed. Ahora preparar_base() hace
        # migraciones + seed una sola vez, y solo si cambió su código.
        try:
            preparar_base()
        except Exception:
            logger.exception("Error en migraciones")
        app._migrations_applied = True


if __name__ == "__main__":
    # Inicializar BD si no existe
    with app.app_context():
        preparar_base()

    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        with app.app_context():
            init_db()
        logger.info("Base de datos inicializada.")
    else:
        # debug=True nunca debe quedar hardcodeado: expone un traceback
        # interactivo con ejecución de código si esto llegara a correr en
        # producción por error. Por defecto False; se habilita solo si se
        # setea explícitamente FLASK_DEBUG=1 en el entorno (uso local).
        debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
        app.run(debug=debug_mode)
 