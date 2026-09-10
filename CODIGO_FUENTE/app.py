import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask

from CODIGO_FUENTE.blueprints.admin import admin_bp
from CODIGO_FUENTE.blueprints.api import api_bp
from CODIGO_FUENTE.blueprints.auth import auth_bp
from CODIGO_FUENTE.blueprints.dml import dml_bp
from CODIGO_FUENTE.blueprints.envios import envios_bp
from CODIGO_FUENTE.blueprints.estadisticas import estadisticas_bp
from CODIGO_FUENTE.blueprints.notificaciones import notificaciones_bp
from CODIGO_FUENTE.blueprints.raypac import raypac_bp
from CODIGO_FUENTE.blueprints.stock import stock_bp
from CODIGO_FUENTE.blueprints.tickets import tickets_bp
from CODIGO_FUENTE.config import BASE_DIR, Config
from CODIGO_FUENTE.decorators import get_current_user_jinja
from CODIGO_FUENTE.extensions import close_db, init_db, migrate_db
from CODIGO_FUENTE.services.stock import get_alert_badge

load_dotenv()

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
 
logger = logging.getLogger(__name__)

# Hacer funciones de negocio disponibles en todos los templates Jinja2
app.jinja_env.globals.update(
    get_current_user=get_current_user_jinja,
    get_alert_badge=get_alert_badge,
    current_year=lambda: datetime.now().year,
)

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

@app.before_request
def apply_migrations():
    """Aplica migraciones de BD al iniciar la app."""
    if not hasattr(app, '_migrations_applied'):
        try:
            # Si la BD no existe, crearla (init_db incluye seed automático)
            db_path = app.config["DATABASE"]
            if not os.path.exists(db_path):
                logger.info("Base de datos no encontrada. Inicializando...")
                init_db()
            else:
                # Si existe, aplicar migraciones
                migrate_db()

            # Verificar/crear usuarios siempre, exista o no la base
            from CODIGO_FUENTE.extensions import get_db
            from CODIGO_FUENTE.services.seed import load_seed_data
            load_seed_data(get_db())

        except Exception:
            logger.exception("Error en migraciones")
        app._migrations_applied = True


if __name__ == "__main__":
    # Inicializar BD si no existe
    with app.app_context():
        db_path = app.config["DATABASE"]
        if not os.path.exists(db_path):
            logger.info("Creando base de datos...")
            init_db()
            logger.info("Base de datos creada exitosamente")
        else:
            # Aplicar migraciones a BD existente
            migrate_db()

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
 