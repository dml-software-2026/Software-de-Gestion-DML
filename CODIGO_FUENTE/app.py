import os
import sys

from dotenv import load_dotenv
from flask import Flask

from CODIGO_FUENTE.config import Config, BASE_DIR
from CODIGO_FUENTE.extensions import close_db, init_db, migrate_db
from CODIGO_FUENTE.decorators import get_current_user_jinja

from CODIGO_FUENTE.blueprints.auth import auth_bp
from CODIGO_FUENTE.blueprints.raypac import raypac_bp
from CODIGO_FUENTE.blueprints.dml import dml_bp
from CODIGO_FUENTE.blueprints.tickets import tickets_bp
from CODIGO_FUENTE.blueprints.envios import envios_bp
from CODIGO_FUENTE.blueprints.stock import stock_bp
from CODIGO_FUENTE.blueprints.admin import admin_bp
from CODIGO_FUENTE.blueprints.estadisticas import estadisticas_bp
from CODIGO_FUENTE.blueprints.api import api_bp

load_dotenv()

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "INTERFAZ", "templates"),
    static_folder=os.path.join(BASE_DIR, "INTERFAZ", "static"),
    static_url_path="/static"
)
app.config.from_object(Config)

# Hacer get_current_user disponible en todos los templates Jinja2
app.jinja_env.globals.update(get_current_user=get_current_user_jinja)

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


@app.before_request
def apply_migrations():
    """Aplica migraciones de BD al iniciar la app."""
    if not hasattr(app, '_migrations_applied'):
        try:
            # Si la BD no existe, crearla (init_db incluye seed automático)
            db_path = app.config["DATABASE"]
            if not os.path.exists(db_path):
                print("📁 Base de datos no encontrada. Inicializando...")
                init_db()
            else:
                # Si existe, aplicar migraciones
                migrate_db()
        except Exception as e:
            print(f"Error en migraciones: {e}")
            import traceback
            traceback.print_exc()
        app._migrations_applied = True


if __name__ == "__main__":
    # Inicializar BD si no existe
    with app.app_context():
        db_path = app.config["DATABASE"]
        if not os.path.exists(db_path):
            print("[DB] Creando base de datos...")
            init_db()
            print("[DB] Base de datos creada exitosamente")
        else:
            # Aplicar migraciones a BD existente
            migrate_db()

    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        with app.app_context():
            init_db()
        print("Base de datos inicializada.")
    else:
        app.run(debug=True)
