import os
import sys

# Detectar si es ejecutable compilado
IS_EXECUTABLE = getattr(sys, 'frozen', False)
if IS_EXECUTABLE:
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.path.join(BASE_DIR, "dml.db")
    DATABASE_URL = os.getenv("DATABASE_URL")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    MAIL_FROM = os.getenv("MAIL_FROM", "onboarding@resend.dev")
    MAIL_DEV_REDIRECT = os.getenv("MAIL_DEV_REDIRECT")
    # #311: clave que manda el workflow de GitHub para pedir el backup semanal.
    # Sin esta variable, /admin/backup/auto no hace nada.
    BACKUP_AUTO_TOKEN = os.getenv("BACKUP_AUTO_TOKEN")
    # #379: la cookie de sesión no viaja en formularios que vienen de otros
    # sitios (Lax) y, en Render (siempre HTTPS), solo viaja por HTTPS. En
    # local es http, por eso Secure va solo con la variable RENDER.
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool(os.getenv("RENDER"))


# #327: técnicos del ST de DML. Única fuente de la lista: ticket_nuevo.html
# y dml_edit.html arman el <select> a partir de esta constante
# (global de Jinja, ver app.py) y el backend rechaza cualquier otro valor.
# Para sumar un técnico, agregarlo acá. Las fichas/tickets viejos con otro
# texto no se migran: se siguen mostrando como están.
TECNICOS_ST = ["Ricardo", "David"]

# #331: mano de obra de la ficha, una sola opción por ficha (opcional). Las
# 5 primeras son las de la ficha en papel 2026 (se marcaban con una x);
# "En garantía" la pidió David (2026-11-15). Única fuente de la lista: el
# <select> de dml_edit.html (global de Jinja) y la validación de dml_edit().
MANO_DE_OBRA_OPCIONES = [
    "Módulo reparación base (3 hs) - máquina batería o neumática",
    "Módulo reparación base (3 hs) - máquina manual",
    "Costo presupuesto - máquina batería o neumática",
    "Costo presupuesto - máquina manual",
    "Sin cargo",
    "En garantía",
]
