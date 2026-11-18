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


# #327: técnicos del ST de DML. Única fuente de la lista: ticket_nuevo.html
# y dml_edit.html arman el <select> a partir de esta constante
# (global de Jinja, ver app.py) y el backend rechaza cualquier otro valor.
# Para sumar un técnico, agregarlo acá. Las fichas/tickets viejos con otro
# texto no se migran: se siguen mostrando como están.
TECNICOS_ST = ["Ricardo", "David"]
