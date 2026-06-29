import os
import sys
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import json

from flask import (
    Flask, g, render_template, request, redirect,
    url_for, session, flash, send_file, jsonify
)

load_dotenv()

# Ruta base del proyecto (se calcula desde la ubicación de este archivo)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "INTERFAZ", "templates"),
    static_folder=os.path.join(BASE_DIR, "INTERFAZ", "static"),
    static_url_path="/static"
)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
    DATABASE=os.path.join(BASE_DIR, "dml.db"),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "localhost"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", True),
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "noreply@dml.local")
)

# Hacer funciones disponibles en Jinja2
def get_current_user_jinja():
    """Obtiene usuario actual para uso en Jinja2"""
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

app.jinja_env.globals.update(get_current_user=get_current_user_jinja)

# ======================== DATABASE ========================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def migrate_db():
    """Ejecuta migraciones de esquema necesarias."""
    db = get_db()
    try:
        # Verificar si la columna cantidad_utilizada existe
        cursor = db.execute("PRAGMA table_info(dml_repuestos)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'cantidad_utilizada' not in columns:
            db.execute("ALTER TABLE dml_repuestos ADD COLUMN cantidad_utilizada INTEGER DEFAULT 1")
            db.commit()
            
        if 'estado_repuesto' not in columns:
            db.execute("ALTER TABLE dml_repuestos ADD COLUMN estado_repuesto TEXT DEFAULT 'INSPECCIONADO'")
            db.commit()
    except Exception as e:
        pass  # Las columnas ya existen o la tabla no existe

def init_db():
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()
    migrate_db()  # Aplicar migraciones

# ======================== HELPERS ========================

def send_mail(to_email, subject, html_body):
    """Envía mail con manejo de errores."""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            if app.config['MAIL_USE_TLS']:
                server.starttls()
            if app.config['MAIL_USERNAME']:
                server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Error sending mail: {e}")
        return False

def log_action(user_id, action, table_name, record_id=None, old_value=None, new_value=None):
    """Registra acción en auditoría."""
    db = get_db()
    db.execute(
        """INSERT INTO audit_log 
           (user_id, action, table_name, record_id, old_value, new_value)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, action, table_name, record_id, old_value, new_value)
    )
    db.commit()

def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = get_current_user()
            if user["role"] not in roles:
                flash("No tienes permiso para acceder a esta página.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

def check_stock_alert(codigo):
    """Verifica nivel de stock y retorna estado de alerta."""
    db = get_db()
    stock = db.execute("SELECT cantidad FROM stock_dml WHERE codigo_repuesto = ?", (codigo,)).fetchone()
    
    if not stock:
        return "NO_EXISTE"
    
    qty = stock['cantidad']
    if qty == 0:
        return "ROJO"  # Falta completamente
    elif qty == 1:
        return "AMARILLO"  # Último repuesto
    elif qty == 2:
        return "NARANJA"  # Pocos repuestos
    else:
        return "OK"

def generate_ficha_number():
    """Genera el próximo número de ficha correlativo."""
    db = get_db()
    last = db.execute("SELECT MAX(numero_ficha) as max FROM dml_fichas").fetchone()
    return (last['max'] or 500) + 1

def generate_ticket_number(serial):
    """Genera número de ticket basado en número de serie."""
    db = get_db()
    year = datetime.now().year
    count = db.execute("SELECT COUNT(*) as total FROM dml_fichas WHERE strftime('%Y', created_at) = ?", (str(year),)).fetchone()
    ticket_num = count['total'] + 1
    return f"TK-{year}-{serial.upper()}-{ticket_num:05d}"

# ======================== AUTH ========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        print(f"[LOGIN] Intento - Email: {email}, Password: {'*' * len(password)}")
        
        if not email or not password:
            flash("Email y contraseña son requeridos.", "error")
            return render_template("login.html")
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        print(f"[LOGIN] Usuario encontrado: {user is not None}")
        
        if user:
            print(f"[LOGIN] Hash en BD: {user['password_hash'][:50]}...")
            pwd_match = check_password_hash(user["password_hash"], password)
            print(f"[LOGIN] Contraseña coincide: {pwd_match}")
            
            if pwd_match:
                if not user["is_active"]:
                    flash("Usuario desactivado.", "error")
                    return render_template("login.html")
                session["user_id"] = user["id"]
                session.modified = True
                flash(f"Bienvenido {email}", "success")
                print(f"[LOGIN] Sesion creada para user_id: {user['id']}")
                return redirect(url_for("index"))
        
        flash("Credenciales inválidas.", "error")
        print(f"[LOGIN] Credenciales rechazadas para {email}")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    user = get_current_user()
    db = get_db()
    
    stats = {
        "raypac_total": db.execute("SELECT COUNT(*) as total FROM raypac_entries").fetchone()['total'],
        "dml_en_proceso": db.execute("SELECT COUNT(*) as total FROM dml_fichas WHERE is_closed = 0").fetchone()['total'],
        "dml_completadas": db.execute("SELECT COUNT(*) as total FROM dml_fichas WHERE is_closed = 1").fetchone()['total'],
        "stock_bajo": db.execute("SELECT COUNT(*) as total FROM stock_dml WHERE cantidad <= 2").fetchone()['total']
    }
    
    return render_template("index.html", user=user, stats=stats)

# ======================== APLICAR MIGRACIONES AL INICIAR ========================

@app.before_request
def apply_migrations():
    """Aplica migraciones de BD al iniciar la app"""
    if not hasattr(app, '_migrations_applied'):
        try:
            migrate_db()
        except Exception as e:
            pass  # Las columnas ya existen o hay otro problema
        app._migrations_applied = True

# ======================== RAYPAC ========================

@app.route("/raypac")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_ST")
def raypac_list():
    db = get_db()
    entries = db.execute("""
        SELECT * FROM raypac_entries 
        ORDER BY created_at DESC
    """).fetchall()
    
    return render_template("raypac_list.html", entries=entries)

@app.route("/raypac/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_new():
    user = get_current_user()
    db = get_db()
    
    if request.method == "POST":
        try:
            fecha = request.form.get("fecha_recepcion") or datetime.now().strftime("%Y-%m-%d")
            tipo_solicitud = request.form.get("tipo_solicitud")
            cliente = request.form.get("cliente")
            numero_serie = request.form.get("numero_serie")
            modelo = request.form.get("modelo_maquina")
            tipo_maquina = request.form.get("tipo_maquina")
            numero_bateria = request.form.get("numero_bateria") or "NO APLICA"
            numero_cargador = request.form.get("numero_cargador") or "NO APLICA"
            diagnostico = request.form.get("diagnostico_ingreso")
            comercial = request.form.get("comercial")
            mail_comercial = request.form.get("mail_comercial")
            
            # Validación básica
            if not all([tipo_solicitud, cliente, numero_serie, modelo, tipo_maquina, comercial, mail_comercial]):
                flash("Por favor completa todos los campos obligatorios.", "error")
                return render_template("raypac_form.html")
            
            # Verificar que el número de serie es único
            existe = db.execute("SELECT id FROM raypac_entries WHERE numero_serie = ?", (numero_serie,)).fetchone()
            if existe:
                flash("Este número de serie ya existe en el sistema.", "error")
                return render_template("raypac_form.html")
            
            db.execute("""
                INSERT INTO raypac_entries 
                (fecha_recepcion, tipo_solicitud, cliente, numero_serie, modelo_maquina, tipo_maquina,
                 numero_bateria, numero_cargador, diagnostico_ingreso, comercial, mail_comercial)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, tipo_solicitud, cliente, numero_serie, modelo, tipo_maquina,
                  numero_bateria, numero_cargador, diagnostico, comercial, mail_comercial))
            db.commit()
            
            raypac_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
            log_action(user['id'], "CREATE", "raypac_entries", raypac_id, None, 
                      f"Ingreso RAYPAC: {cliente} - {numero_serie}")
            
            flash("Ingreso RAYPAC registrado correctamente.", "success")
            return redirect(url_for("raypac_view", id=raypac_id))
        except Exception as e:
            flash(f"Error al guardar: {str(e)}", "error")
            return render_template("raypac_form.html")
    
    return render_template("raypac_form.html")

@app.route("/raypac/<int:id>")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_ST")
def raypac_view(id):
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    return render_template("raypac_view.html", entry=entry)

@app.route("/raypac/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_edit(id):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    if entry['is_frozen'] and not request.form.get("unfreeze_code"):
        flash("Este registro está freezado. Requiere código de desbloqueo.", "error")
        return render_template("raypac_view.html", entry=entry)
    
    if request.method == "POST":
        try:
            unfreeze_code = request.form.get("unfreeze_code")
            if entry['is_frozen'] and unfreeze_code != "ADMIN2024":
                flash("Código de desbloqueo incorrecto.", "error")
                return render_template("raypac_view.html", entry=entry)
            
            fecha = request.form.get("fecha_recepcion")
            tipo_solicitud = request.form.get("tipo_solicitud")
            cliente = request.form.get("cliente")
            numero_serie = request.form.get("numero_serie")
            diagnostico = request.form.get("diagnostico_ingreso")
            comercial = request.form.get("comercial")
            mail_comercial = request.form.get("mail_comercial")
            
            db.execute("""
                UPDATE raypac_entries 
                SET fecha_recepcion=?, tipo_solicitud=?, cliente=?, numero_serie=?,
                    diagnostico_ingreso=?, comercial=?, mail_comercial=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ?
            """, (fecha, tipo_solicitud, cliente, numero_serie, diagnostico, comercial, mail_comercial, id))
            db.commit()
            
            log_action(user['id'], "UPDATE", "raypac_entries", id, None, 
                      f"Actualización: {cliente}")
            
            flash("Ingreso RAYPAC actualizado.", "success")
            return redirect(url_for("raypac_view", id=id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template("raypac_form.html", entry=entry, edit=True)

@app.route("/raypac/<int:id>/freeze", methods=["POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_freeze(id):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    numero_remito = request.form.get("numero_remito")
    if not numero_remito:
        flash("Por favor ingresa el número de remito.", "error")
        return redirect(url_for("raypac_view", id=id))
    
    db.execute("""
        UPDATE raypac_entries 
        SET is_frozen = 1, frozen_at = CURRENT_TIMESTAMP, numero_remito = ?
        WHERE id = ?
    """, (numero_remito, id))
    db.commit()
    
    log_action(user['id'], "FREEZE", "raypac_entries", id, None, 
              f"Freezado con remito {numero_remito}")
    
    flash("Máquina freezada y enviada a ST.", "success")
    return redirect(url_for("raypac_view", id=id))

@app.route("/raypac/<int:id>/unfreeze", methods=["POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_unfreeze(id):
    """Descongelar un ingreso RAYPAC con código"""
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    if not entry['is_frozen']:
        flash("El registro no está freezado.", "error")
        return redirect(url_for("raypac_view", id=id))
    
    unfreeze_code = request.form.get("unfreeze_code", "").strip()
    
    # Verificar código (usar número de remito como referencia simple)
    if unfreeze_code != entry['numero_remito']:
        flash("Código de descongelamiento incorrecto.", "error")
        return redirect(url_for("raypac_view", id=id))
    
    db.execute("""
        UPDATE raypac_entries 
        SET is_frozen = 0, frozen_at = NULL
        WHERE id = ?
    """, (id,))
    db.commit()
    
    log_action(user['id'], "UNFREEZE", "raypac_entries", id, None, "Descongelado")
    
    flash("Máquina descongelada correctamente.", "success")
    return redirect(url_for("raypac_view", id=id))

# ======================== DML - FICHAS ========================

@app.route("/dml")
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def dml_list():
    db = get_db()
    fichas = db.execute("""
        SELECT f.*, r.cliente, r.numero_serie 
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        ORDER BY f.created_at DESC
    """).fetchall()
    
    return render_template("dml_list.html", fichas=fichas)

@app.route("/dml/new/<int:raypac_id>", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_new(raypac_id):
    user = get_current_user()
    db = get_db()
    
    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (raypac_id,)).fetchone()
    if not raypac:
        flash("Ingreso RAYPAC no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    if request.method == "POST":
        try:
            fecha_ingreso = request.form.get("fecha_ingreso") or datetime.now().strftime("%Y-%m-%d")
            tecnico = request.form.get("tecnico")
            diagnostico = request.form.get("diagnostico_inicial")
            observaciones = request.form.get("observaciones")
            n_ciclos = request.form.get("n_ciclos") or 0
            tecnico_resp = request.form.get("tecnico_resp")
            
            if not all([tecnico, tecnico_resp]):
                flash("Completa los campos obligatorios.", "error")
                return render_template("dml_form.html", raypac=raypac)
            
            numero_ficha = generate_ficha_number()
            numero_ticket = generate_ticket_number(raypac['numero_serie'])
            
            db.execute("""
                INSERT INTO dml_fichas 
                (numero_ficha, raypac_id, fecha_ingreso, tecnico, numero_ticket,
                 diagnostico_inicial, observaciones, n_ciclos, tecnico_resp,
                 estado_reparacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (numero_ficha, raypac_id, fecha_ingreso, tecnico, numero_ticket,
                  diagnostico, observaciones, n_ciclos, tecnico_resp, 'A LA ESPERA DE REVISIÓN'))
            db.commit()
            
            ficha_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
            
            # Crear partes estándar
            partes = [
                "ESTADO DEL EQUIPO", "CARCAZA", "CUBRE FEEDWHEEL", "MANGO",
                "BOTONES", "MOTOR DE ARRASTRE", "MOTOR DE SELLADO", "CUCHILLA",
                "SERVO", "RUEDA DE ARRASTRE", "RESORTE DE MANIJA", "OTROS"
            ]
            for parte in partes:
                db.execute(
                    "INSERT INTO dml_partes (ficha_id, nombre_parte, estado) VALUES (?, ?, ?)",
                    (ficha_id, parte, "POR INSPECCIONAR")
                )
            db.commit()
            
            log_action(user['id'], "CREATE", "dml_fichas", ficha_id, None,
                      f"Ficha DML #{numero_ficha}")
            
            flash(f"Ficha #{numero_ficha} creada correctamente. Ticket: {numero_ticket}", "success")
            return redirect(url_for("dml_view", id=ficha_id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return render_template("dml_form.html", raypac=raypac)
    
    return render_template("dml_form.html", raypac=raypac)

@app.route("/dml/<int:id>")
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def dml_view(id):
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    # Obtener datos de RAYPAC
    raypac = None
    if ficha['raypac_id']:
        raypac = db.execute(
            "SELECT * FROM raypac_entries WHERE id = ?",
            (ficha['raypac_id'],)
        ).fetchone()
    
    partes = db.execute(
        "SELECT * FROM dml_partes WHERE ficha_id = ? ORDER BY id",
        (id,)
    ).fetchall()
    
    repuestos = db.execute(
        "SELECT * FROM dml_repuestos WHERE ficha_id = ? ORDER BY id",
        (id,)
    ).fetchall()
    
    return render_template("dml_view.html", ficha=ficha, raypac=raypac, partes=partes, repuestos=repuestos)

@app.route("/dml/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_edit(id):
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    if ficha['is_closed'] and not request.form.get("unfreeze_code"):
        flash("Esta ficha está cerrada. Requiere código para editar.", "error")
        return redirect(url_for("dml_view", id=id))
    
    if request.method == "POST":
        try:
            unfreeze_code = request.form.get("unfreeze_code")
            if ficha['is_closed'] and unfreeze_code != "ADMIN2024":
                flash("Código incorrecto.", "error")
                return redirect(url_for("dml_view", id=id))
            
            # Capturar SOLO los campos editables (no los de RAYPAC)
            fecha_ingreso = request.form.get("fecha_ingreso")
            fecha_egreso = request.form.get("fecha_egreso")
            
            estado = request.form.get("estado_reparacion")
            diagnostico = request.form.get("diagnostico_inicial")
            diagnostico_rep = request.form.get("diagnostico_reparacion")
            observaciones = request.form.get("observaciones")
            n_ciclos = request.form.get("n_ciclos")
            mecanizado = request.form.get("mecanizado_adic") or "NO APLICA"
            horas = request.form.get("horas_adic") or 0
            numero_remito = request.form.get("numero_remito_salida")
            tecnico_resp = request.form.get("tecnico_resp") or ""
            
            # Actualizar SOLO los campos que existen en dml_fichas
            db.execute("""
                UPDATE dml_fichas 
                SET fecha_ingreso=?, fecha_egreso=?,
                    estado_reparacion=?, diagnostico_inicial=?, diagnostico_reparacion=?, observaciones=?,
                    n_ciclos=?, mecanizado_adic=?, horas_adic=?, numero_remito_salida=?,
                    tecnico_resp=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ?
            """, (fecha_ingreso, fecha_egreso,
                  estado, diagnostico, diagnostico_rep, observaciones,
                  n_ciclos, mecanizado, horas, numero_remito,
                  tecnico_resp, id))
            db.commit()
            
            # Actualizar partes
            partes = db.execute("SELECT id FROM dml_partes WHERE ficha_id = ? ORDER BY id", (id,)).fetchall()
            for idx, parte in enumerate(partes):
                estado_parte = request.form.get(f"parte_{idx}")
                if estado_parte:
                    db.execute(
                        "UPDATE dml_partes SET estado = ? WHERE id = ?",
                        (estado_parte, parte['id'])
                    )
            db.commit()
            
            log_action(user['id'], "UPDATE", "dml_fichas", id, None, f"Actualización ficha")
            
            flash("Ficha actualizada correctamente.", "success")
            return redirect(url_for("dml_view", id=id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = ?", (id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = ?", (id,)).fetchall()
    
    return render_template("dml_edit.html", ficha=ficha, partes=partes, repuestos=repuestos)

# ======================== REPUESTOS ========================

@app.route("/dml/<int:id>/repuestos/agregar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def agregar_repuesto(id):
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_view", id=id))
    
    # Validar cantidad máxima (15 repuestos)
    count = db.execute("SELECT COUNT(*) as cnt FROM dml_repuestos WHERE ficha_id = ?", (id,)).fetchone()
    if count['cnt'] >= 15:
        flash("Máximo 15 repuestos por ficha.", "error")
        return redirect(url_for("dml_view", id=id))
    
    codigo = request.form.get("codigo_repuesto", "").strip()
    cantidad = int(request.form.get("cantidad", 1))
    cantidad_utilizada = int(request.form.get("cantidad_utilizada", 1))
    estado_repuesto = request.form.get("estado_repuesto", "").strip()
    
    # Validar campos obligatorios
    if not codigo or not cantidad or not cantidad_utilizada or not estado_repuesto:
        flash("Todos los campos son obligatorios.", "error")
        return redirect(url_for("dml_view", id=id))
    
    # Buscar repuesto en matriz
    repuesto = db.execute(
        "SELECT * FROM matriz_repuestos WHERE codigo_repuesto = ?",
        (codigo,)
    ).fetchone()
    
    if not repuesto:
        flash(f"Repuesto '{codigo}' no encontrado en matriz.", "error")
        return redirect(url_for("dml_view", id=id))
    
    # Verificar stock
    stock = db.execute(
        "SELECT cantidad FROM stock_dml WHERE codigo_repuesto = ?",
        (codigo,)
    ).fetchone()
    
    en_stock = 1 if stock and stock['cantidad'] >= cantidad else 0
    en_falta = 1 if not en_stock else 0
    
    # Insertar repuesto con nuevos campos
    db.execute("""
        INSERT INTO dml_repuestos 
        (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (id, codigo, repuesto['item'], cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta))
    db.commit()
    
    # Actualizar stock si hay disponibilidad
    if en_stock:
        db.execute(
            "UPDATE stock_dml SET cantidad = cantidad - ? WHERE codigo_repuesto = ?",
            (cantidad, codigo)
        )
        db.commit()
    
    log_action(user['id'], "ADD_PART", "dml_repuestos", id, None, 
              f"{codigo} x{cantidad} (util:{cantidad_utilizada}, estado:{estado_repuesto})")
    
    flash(f"Repuesto '{codigo}' agregado correctamente.", "success")
    return redirect(url_for("dml_view", id=id))

@app.route("/dml/<int:id>/marcar-falta/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def marcar_repuesto_falta(id, repuesto_id):
    db = get_db()
    
    repuesto = db.execute(
        "SELECT * FROM dml_repuestos WHERE id = ? AND ficha_id = ?",
        (repuesto_id, id)
    ).fetchone()
    
    if not repuesto:
        return jsonify({"error": "Repuesto no encontrado"}), 404
    
    db.execute(
        "UPDATE dml_repuestos SET en_falta = 1, en_stock = 0 WHERE id = ?",
        (repuesto_id,)
    )
    db.commit()
    
    return jsonify({"success": True}), 200

@app.route("/dml/<int:id>/marcar-llegada/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def marcar_repuesto_llegada(id, repuesto_id):
    db = get_db()
    user = get_current_user()
    
    repuesto = db.execute(
        "SELECT * FROM dml_repuestos WHERE id = ? AND ficha_id = ?",
        (repuesto_id, id)
    ).fetchone()
    
    if not repuesto:
        return jsonify({"error": "Repuesto no encontrado"}), 404
    
    # Cambiar estado
    db.execute(
        "UPDATE dml_repuestos SET en_falta = 0, en_stock = 1 WHERE id = ?",
        (repuesto_id,)
    )
    
    # Actualizar stock
    db.execute(
        "UPDATE stock_dml SET cantidad = cantidad - ? WHERE codigo_repuesto = ?",
        (repuesto['cantidad'], repuesto['codigo_repuesto'])
    )
    db.commit()
    
    log_action(user['id'], "PART_ARRIVED", "dml_repuestos", repuesto_id, None,
              f"{repuesto['codigo_repuesto']}")
    
    return jsonify({"success": True}), 200

@app.route("/dml/<int:ficha_id>/repuestos/eliminar/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def eliminar_repuesto(ficha_id, repuesto_id):
    user = get_current_user()
    db = get_db()
    
    repuesto = db.execute("SELECT * FROM dml_repuestos WHERE id = ? AND ficha_id = ?", (repuesto_id, ficha_id)).fetchone()
    if not repuesto:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("dml_view", id=ficha_id))
    
    # Si el repuesto estaba en stock, devolverlo
    if repuesto['en_stock']:
        db.execute(
            "UPDATE stock_dml SET cantidad = cantidad + ? WHERE codigo_repuesto = ?",
            (repuesto['cantidad'], repuesto['codigo_repuesto'])
        )
        db.commit()
    
    # Eliminar repuesto
    db.execute("DELETE FROM dml_repuestos WHERE id = ?", (repuesto_id,))
    db.commit()
    
    log_action(user['id'], "DELETE", "dml_repuestos", repuesto_id, None,
              f"Repuesto {repuesto['codigo_repuesto']} eliminado de ficha {ficha_id}")
    
    flash("Repuesto eliminado correctamente.", "success")
    return redirect(url_for("dml_view", id=ficha_id))

# ======================== STOCK ========================

@app.route("/stock")
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "RAYPAC")
def stock_list():
    user = get_current_user()
    db = get_db()
    
    ubicacion = request.args.get("ubicacion", "DML")
    buscar = request.args.get("buscar", "")
    
    query = "SELECT * FROM stock_dml WHERE 1=1"
    params = []
    
    if buscar:
        query += " AND (codigo_repuesto LIKE ? OR item LIKE ?)"
        params = [f"%{buscar}%", f"%{buscar}%"]
    
    stocks = db.execute(query + " ORDER BY codigo_repuesto", params).fetchall()
    
    # Agregar información de alerta
    stocks_con_alerta = []
    for stock in stocks:
        alerta = check_stock_alert(stock['codigo_repuesto'])
        stocks_con_alerta.append({
            **dict(stock),
            'alerta': alerta
        })
    
    return render_template("stock_list.html", user=user, rows=stocks_con_alerta, ubicacion=ubicacion)

@app.route("/stock/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def stock_new():
    user = get_current_user()
    db = get_db()
    
    if request.method == "POST":
        try:
            codigo = request.form.get("codigo_repuesto")
            item = request.form.get("item")
            cantidad = int(request.form.get("cantidad", 0))
            cantidad_min = int(request.form.get("cantidad_minima", 2))
            
            if not codigo or not item:
                flash("Código e Item son obligatorios.", "error")
                return render_template("stock_new.html")
            
            # Verificar que no exista
            existe = db.execute(
                "SELECT id FROM matriz_repuestos WHERE codigo_repuesto = ?",
                (codigo,)
            ).fetchone()
            
            if existe:
                flash("Este código ya existe.", "error")
                return render_template("stock_new.html")
            
            # Insertar en matriz
            numero = db.execute("SELECT MAX(numero) as max FROM matriz_repuestos").fetchone()['max'] or 0
            db.execute("""
                INSERT INTO matriz_repuestos 
                (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (numero + 1, codigo, item, cantidad, cantidad, "DML"))
            
            # Insertar en stock
            db.execute("""
                INSERT INTO stock_dml 
                (codigo_repuesto, item, cantidad, cantidad_minima)
                VALUES (?, ?, ?, ?)
            """, (codigo, item, cantidad, cantidad_min))
            db.commit()
            
            log_action(user['id'], "CREATE", "stock_dml", None, None, f"{codigo} - {item}")
            
            flash(f"Repuesto {codigo} agregado al stock.", "success")
            return redirect(url_for("stock_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return render_template("stock_new.html")
    
    return render_template("stock_new.html")

@app.route("/stock/<codigo>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def stock_edit(codigo):
    user = get_current_user()
    db = get_db()
    
    stock = db.execute(
        "SELECT * FROM stock_dml WHERE codigo_repuesto = ?",
        (codigo,)
    ).fetchone()
    
    if not stock:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("stock_list"))
    
    if request.method == "POST":
        try:
            cantidad = int(request.form.get("cantidad", 0))
            cantidad_min = int(request.form.get("cantidad_minima", 2))
            
            db.execute("""
                UPDATE stock_dml 
                SET cantidad = ?, cantidad_minima = ?, updated_at = CURRENT_TIMESTAMP
                WHERE codigo_repuesto = ?
            """, (cantidad, cantidad_min, codigo))
            db.commit()
            
            log_action(user['id'], "UPDATE", "stock_dml", None, 
                      f"Anterior: {stock['cantidad']}", f"Nuevo: {cantidad}")
            
            flash("Stock actualizado.", "success")
            return redirect(url_for("stock_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template("stock_edit.html", stock=stock)

@app.route("/stock/<codigo>/delete", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def stock_delete(codigo):
    user = get_current_user()
    db = get_db()
    
    db.execute("DELETE FROM stock_dml WHERE codigo_repuesto = ?", (codigo,))
    db.commit()
    
    log_action(user['id'], "DELETE", "stock_dml", None, codigo, None)
    
    flash("Repuesto eliminado del stock.", "success")
    return redirect(url_for("stock_list"))

# ======================== PDF GENERATION ========================

def generate_ficha_pdf(ficha_id):
    """Genera PDF idéntico al template de Excel CAMPOS DE INGRESO DML4."""
    try:
        db = get_db()
        ficha = db.execute("""
            SELECT f.*, r.cliente, r.numero_serie, r.modelo_maquina, r.comercial, r.mail_comercial, r.numero_remito
            FROM dml_fichas f
            LEFT JOIN raypac_entries r ON f.raypac_id = r.id
            WHERE f.id = ?
        """, (ficha_id,)).fetchone()
        
        if not ficha:
            raise ValueError(f"No se encontró ficha con ID {ficha_id}")
        
        partes = db.execute(
            "SELECT * FROM dml_partes WHERE ficha_id = ? ORDER BY id",
            (ficha_id,)
        ).fetchall()
        
        repuestos = db.execute(
            "SELECT * FROM dml_repuestos WHERE ficha_id = ? ORDER BY id",
            (ficha_id,)
        ).fetchall()
        
        ficha_dict = dict(ficha) if ficha else {}
        
        # Crear PDF con márgenes compactos
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch, 
                               leftMargin=0.4*inch, rightMargin=0.4*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        # Colores exactos del template
        yellow = colors.HexColor('#FFFF00')
        gray = colors.HexColor('#C0C0C0')
        dark_blue = colors.HexColor('#003366')
        black = colors.black
        white = colors.white
        
        # Estilos simplificados
        title_big = ParagraphStyle('TitleBig', parent=styles['Normal'], fontSize=14, 
                                   fontName='Helvetica-Bold', textColor=black, alignment=0)
        num_ficha = ParagraphStyle('NumFicha', parent=styles['Normal'], fontSize=11,
                                   fontName='Helvetica-Bold', textColor=black)
        label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=8.5,
                              fontName='Helvetica-Bold', textColor=black)
        value = ParagraphStyle('Value', parent=styles['Normal'], fontSize=8, textColor=black)
        section_header = ParagraphStyle('SectionHeader', parent=styles['Normal'], fontSize=9,
                                       fontName='Helvetica-Bold', textColor=black,
                                       backColor=gray)
        normal_text = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=8, textColor=black)
        
        # ============ SECCIÓN 1: ENCABEZADO ============
        header_data = [
            [Paragraph("INFORME DML SOBRE EL EQUIPO EN REVISION", title_big), "", "", "", "", "", "", "", "", ""],
            [Paragraph(f"<b>Nº Ficha:</b> {ficha_dict.get('numero_ficha', '')}", num_ficha), "", "", "", "", "", "", "", "", ""],
            ["500", "Servicio Técnico", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", "", "", ""],
        ]
        
        header_table = Table(header_data, colWidths=[0.7*inch]*10)
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.08*inch))
        
        # ============ SECCIÓN 2: DATOS GENERALES ============
        fecha_ing = str(ficha_dict.get('fecha_ingreso', '') or '')
        comercial = str(ficha_dict.get('comercial', '') or '')
        cliente = str(ficha_dict.get('cliente', '') or '')
        modelo = str(ficha_dict.get('modelo_maquina', '') or '')
        serie = str(ficha_dict.get('numero_serie', '') or '')
        fecha_egr = str(ficha_dict.get('fecha_egreso', '') or '')
        bat = str(ficha_dict.get('numero_bateria', 'NO APLICA') or 'NO APLICA')
        cargador = str(ficha_dict.get('numero_cargador', 'NO APLICA') or 'NO APLICA')
        
        # Tabla de 2 columnas: izquierda y derecha
        gen_data = [
            # Fila 1
            [Paragraph("<b>Fecha de recepción Raypac:</b>", label), Paragraph(fecha_ing, value),
             Paragraph("<b>ESTADO DEL EQUIPO</b>", label), Paragraph("BUENO", value)],
            # Fila 2
            [Paragraph("<b>Comercial responsable:</b>", label), Paragraph(comercial, value),
             Paragraph("<b>CARCAZA</b>", label), Paragraph("OK", value)],
            # Fila 3
            [Paragraph("<b>Nombre del Cliente:</b>", label), Paragraph(cliente, value),
             Paragraph("<b>CUBRE FEEDWHEEL</b>", label), Paragraph("OK", value)],
            # Fila 4
            [Paragraph("<b>Equipo Recibido:</b>", label), Paragraph(modelo, value),
             Paragraph("<b>MANGO</b>", label), Paragraph("OK", value)],
            # Fila 5
            [Paragraph(f"<b>Serie N°:</b>", label), Paragraph(serie, value),
             Paragraph("<b>BOTONES</b>", label), Paragraph("OK", value)],
            # Fila 6
            [Paragraph("<b>Fecha de ingreso DML:</b>", label), Paragraph(fecha_ing, value),
             Paragraph("<b>MOTOR DE ARRASTRE</b>", label), Paragraph("OK", value)],
            # Fila 7
            [Paragraph("<b>Fecha de egreso DML:</b>", label), Paragraph(fecha_egr, value),
             Paragraph("<b>Bat N°:</b>", label), Paragraph(bat, value)],
            # Fila 8
            [Paragraph("<b>Cargador N°:</b>", label), Paragraph(cargador, value),
             Paragraph("", value), Paragraph("", value)],
        ]
        
        gen_table = Table(gen_data, colWidths=[1.8*inch, 1.5*inch, 1.8*inch, 1.7*inch])
        gen_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ]))
        elements.append(gen_table)
        elements.append(Spacer(1, 0.08*inch))
        
        # ============ SECCIÓN 3: DIAGNÓSTICO ============
        diag_header = Table([[Paragraph("<b>DIAGNOSTICO DEL DEPARTAMENTO TECNICO</b>", section_header)]],
                           colWidths=[6.8*inch])
        diag_header.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                         ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                         ('TOPPADDING', (0, 0), (-1, -1), 2),
                                         ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        elements.append(diag_header)
        
        diag_text = str(ficha_dict.get('diagnostico_inicial', '') or '')
        diag_box = Table([[Paragraph(diag_text if diag_text else "Sin diagnóstico", normal_text)]], colWidths=[6.8*inch])
        diag_box.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                      ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                      ('TOPPADDING', (0, 0), (-1, -1), 4),
                                      ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                      ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                                      ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch)]))
        elements.append(diag_box)
        elements.append(Spacer(1, 0.06*inch))
        
        # ============ SECCIÓN 4: INTEGRIDAD Y CHEQUEOS ============
        int_header = Table([[Paragraph("<b>INTEGRIDAD Y CHEQUEOS</b>", section_header)]],
                          colWidths=[6.8*inch])
        int_header.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                       ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                       ('TOPPADDING', (0, 0), (-1, -1), 2),
                                       ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        elements.append(int_header)
        
        # Tabla de integridad y chequeos - 2 columnas simples
        int_data = [
            [Paragraph("<b>INTEGRIDAD</b>", label), Paragraph("<b>CHEQUEOS</b>", label)],
            [Paragraph("Armadura de plástico: 80 %", value), Paragraph("Contactos", value)],
            [Paragraph("Base de metal: 80 %", value), Paragraph("Motores", value)],
            [Paragraph("Rueda de tensionado: 80 %", value), Paragraph("Resorte", value)],
            [Paragraph("Sistemas de sellado: 80 %", value), Paragraph("Display", value)],
        ]
        
        int_table = Table(int_data, colWidths=[3.4*inch, 3.4*inch])
        int_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ]))
        elements.append(int_table)
        elements.append(Spacer(1, 0.06*inch))
        
        # ============ SECCIÓN 5: OBSERVACIONES ============
        obs_header = Table([[Paragraph("<b>OBSERVACIONES</b>", section_header)]],
                          colWidths=[6.8*inch])
        obs_header.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                       ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                       ('TOPPADDING', (0, 0), (-1, -1), 2),
                                       ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        elements.append(obs_header)
        
        obs_text = str(ficha_dict.get('observaciones', '') or '')
        obs_box = Table([[Paragraph(obs_text if obs_text else "Sin observaciones", normal_text)]], colWidths=[6.8*inch])
        obs_box.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                    ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                                    ('MINHEIGHT', (0, 0), (-1, -1), 0.8*inch)]))
        elements.append(obs_box)
        elements.append(Spacer(1, 0.06*inch))
        
        # ============ SECCIÓN 6: DIAGNÓSTICO DE REPARACIÓN ============
        diag_rep_header = Table([[Paragraph("<b>DIAGNOSTICO DE REPARACION</b>", section_header)]],
                               colWidths=[6.8*inch])
        diag_rep_header.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                            ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        elements.append(diag_rep_header)
        
        diag_rep_text = str(ficha_dict.get('diagnostico_reparacion', '') or '')
        diag_rep_box = Table([[Paragraph(diag_rep_text if diag_rep_text else "Sin diagnóstico de reparación", normal_text)]], colWidths=[6.8*inch])
        diag_rep_box.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                          ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                          ('TOPPADDING', (0, 0), (-1, -1), 4),
                                          ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                          ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                                          ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch)]))
        elements.append(diag_rep_box)
        elements.append(Spacer(1, 0.06*inch))
        
        # ============ SECCIÓN 7: REPUESTOS COLOCADOS ============
        rep_header = Table([[Paragraph("<b>REPUESTOS COLOCADOS</b>", section_header)]],
                          colWidths=[6.8*inch])
        rep_header.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                       ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                       ('TOPPADDING', (0, 0), (-1, -1), 2),
                                       ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        elements.append(rep_header)
        
        # Tabla de repuestos - EXACTAMENTE como en Excel
        repuestos_data = [
            [Paragraph("<b>Cantidad</b>", label), Paragraph("<b>Codigo</b>", label),
             Paragraph("<b>DESCRIPCION</b>", label), Paragraph("<b>EN STOCK</b>", label),
             Paragraph("<b>EN FALTA</b>", label)]
        ]
        
        # Agregar hasta 15 repuestos (o menos si hay pocos)
        max_repuestos = 15
        for i in range(max_repuestos):
            if i < len(repuestos):
                rep = repuestos[i]
                cantidad = str(rep.get('cantidad_utilizada', rep.get('cantidad', '')))
                codigo = str(rep.get('codigo_repuesto', ''))
                desc = str(rep.get('descripcion', ''))
                en_stock = str(rep.get('en_stock', '')) if rep.get('en_stock') else ''
                en_falta = str(rep.get('en_falta', '')) if rep.get('en_falta') else ''
            else:
                cantidad = "0"
                codigo = "0"
                desc = ""
                en_stock = ""
                en_falta = ""
            
            repuestos_data.append([
                Paragraph(cantidad, value),
                Paragraph(codigo, value),
                Paragraph(desc, value),
                Paragraph(en_stock, value),
                Paragraph(en_falta, value)
            ])
        
        rep_table = Table(repuestos_data, colWidths=[0.7*inch, 0.8*inch, 3.2*inch, 1*inch, 1.1*inch])
        rep_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
        ]))
        elements.append(rep_table)
        elements.append(Spacer(1, 0.08*inch))
        
        # ============ SECCIÓN 8: INFORMACIÓN ADICIONAL ============
        info_rows = [
            [Paragraph(f"<b>N° DE CICLOS DE LA MÁQUINA CON LAS QUE SALE DE ST</b>", label),
             Paragraph(str(ficha_dict.get('n_ciclos', '0')), value), "", "", "", "", ""],
            ["", "", "", "", "", "", ""],
            [Paragraph("<b>MARCAR CON UNA CRUZ LO QUE CORRESPONDA</b>", label), "", "", "", "", "", ""],
            [Paragraph("<b>TIPO DE MAQUINA QUE INGRESO AL ST</b>", label),
             Paragraph("A BATERIA", value), "", "", "", "", ""],
            [Paragraph("El módulo reparación Base es de tres (3hs)", label), "", "", "", "", "", ""],
            [Paragraph("<b>HORAS ADICIONALES DE TRABAJO</b>", label),
             Paragraph(str(ficha_dict.get('horas_adic', 'NO APLICA')), value), "", "", "", "", ""],
            [Paragraph("<b>MECANIZADO ADICIONAL REALIZADO A LA MAQUINA</b>", label),
             Paragraph(str(ficha_dict.get('mecanizado_adic', 'NO APLICA')), value), "", "", "", "", ""],
            [Paragraph("<b>TIPO DE TRABAJO REALIZADO</b>", label),
             Paragraph("REPARACIÓN", value), "", "", "", "", ""],
            [Paragraph("<b>TÉCNICO RESPONSABLE DEL ST DE DML</b>", label),
             Paragraph(str(ficha_dict.get('tecnico_responsable', '')), value), "", "", "", "", ""],
        ]
        
        info_table = Table(info_rows, colWidths=[2.5*inch, 1.2*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.5*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.08*inch))
    
        # ============ FOOTER ============
        footer = Table([
            [Paragraph("<b>SERVICIO TÉCNICO- DML ELECTRICIDAD INDUSTRIAL SRL</b>", 
                      ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, 
                                    fontName='Helvetica-Bold', alignment=1))]
        ], colWidths=[6.8*inch])
        footer.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        elements.append(footer)
        
        doc.build(elements)
        pdf_buffer.seek(0)
        return pdf_buffer
    
    except Exception as e:
        print(f"ERROR en generate_ficha_pdf: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

@app.route("/dml/<int:id>/generar-ficha", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def generar_ficha(id):
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    # Verificar que esté en "MÁQUINA LISTA PARA RETIRAR"
    if ficha['estado_reparacion'] != 'MÁQUINA LISTA PARA RETIRAR':
        flash("La máquina debe estar en estado 'MÁQUINA LISTA PARA RETIRAR'.", "error")
        return redirect(url_for("dml_view", id=id))
    
    try:
        # Generar PDF para validar que no hay errores
        pdf_buffer = generate_ficha_pdf(id)
        
        # Guardar en BD
        db.execute(
            "UPDATE dml_fichas SET ficha_generada = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (id,)
        )
        db.commit()
        
        # Intentar enviar correo al comercial (no bloquear si falla)
        try:
            raypac = db.execute(
                "SELECT mail_comercial FROM raypac_entries WHERE id = ?",
                (ficha['raypac_id'],)
            ).fetchone()
            
            if raypac and raypac['mail_comercial']:
                html_body = f"""
                <html>
                <body>
                <h2>Máquina Lista para Entregar</h2>
                <p>La máquina <strong>{ficha['numero_ficha']}</strong> se encuentra lista para retirar.</p>
                <p>Datos del ticket: {ficha['numero_ticket']}</p>
                <p>Saludos, DML</p>
                </body>
                </html>
                """
                send_mail(raypac['mail_comercial'], 
                         f"Máquina {ficha['numero_ticket']} - Lista para Retirar",
                         html_body)
                
                db.execute(
                    "UPDATE dml_fichas SET ticket_enviado = 1 WHERE id = ?",
                    (id,)
                )
                db.commit()
        except Exception as e:
            print(f"Error al enviar email: {str(e)}")
        
        log_action(user['id'], "GENERATE_FICHA", "dml_fichas", id, None, 
                  f"Ficha #{ficha['numero_ficha']}")
        
        flash("Ficha generada exitosamente. Descarga el PDF con el botón disponible.", "success")
        return redirect(url_for("dml_view", id=id))
        
    except Exception as e:
        flash(f"Error al generar ficha: {str(e)}", "error")
        return redirect(url_for("dml_view", id=id))

@app.route("/dml/<int:id>/pdf", methods=["GET"])
@login_required
@role_required("ADMIN", "DML_ST")
def descargar_ficha_pdf(id):
    """Descarga el PDF de una ficha ya generada."""
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    if not ficha['ficha_generada']:
        flash("La ficha aún no ha sido generada.", "error")
        return redirect(url_for("dml_view", id=id))
    
    # Generar PDF
    pdf_buffer = generate_ficha_pdf(id)
    
    log_action(user['id'], "DOWNLOAD_FICHA_PDF", "dml_fichas", id, None,
              f"Ficha #{ficha['numero_ficha']}")
    
    # Devolver PDF
    return send_file(pdf_buffer, mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"ficha_{ficha['numero_ficha']}.pdf")

# ======================== USUARIOS ========================

@app.route("/admin/usuarios")
@login_required
@role_required("ADMIN")
def usuarios_list():
    db = get_db()
    user = get_current_user()
    usuarios = db.execute("SELECT * FROM users ORDER BY email").fetchall()
    return render_template("usuarios_list.html", usuarios=usuarios, user=user)

@app.route("/admin/usuarios/nueva", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_new():
    user = get_current_user()
    db = get_db()
    
    if request.method == "POST":
        try:
            email = request.form.get("email")
            password = request.form.get("password")
            nombre = request.form.get("nombre")
            role = request.form.get("role")
            
            roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
            
            if not all([email, password, role]):
                flash("Completa los campos obligatorios.", "error")
                return render_template("usuario_form.html", roles=roles)
            
            existe = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existe:
                flash("Este email ya existe.", "error")
                return render_template("usuario_form.html", roles=roles)
            
            hash_pwd = generate_password_hash(password)
            db.execute("""
                INSERT INTO users (email, password_hash, nombre, role, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (email, hash_pwd, nombre, role))
            db.commit()
            
            log_action(user['id'], "CREATE", "users", None, None, f"{email} - {role}")
            
            flash(f"Usuario {email} creado.", "success")
            return redirect(url_for("usuarios_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_form.html", roles=roles)

@app.route("/admin/usuarios/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_edit(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
    
    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios_list"))
    
    if request.method == "POST":
        try:
            nombre = request.form.get("nombre")
            role = request.form.get("role")
            
            db.execute("""
                UPDATE users 
                SET nombre = ?, role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (nombre, role, id))
            db.commit()
            
            log_action(user['id'], "UPDATE", "users", id, None, f"{usuario['email']}")
            
            flash("Usuario actualizado.", "success")
            return redirect(url_for("usuarios_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_edit.html", target_user=usuario, roles=roles)

@app.route("/admin/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
@role_required("ADMIN")
def usuario_toggle(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
    
    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios_list"))
    
    nuevo_estado = 1 - usuario['is_active']
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (nuevo_estado, id))
    db.commit()
    
    log_action(user['id'], "TOGGLE", "users", id, str(usuario['is_active']), str(nuevo_estado))
    
    estado_texto = "activado" if nuevo_estado else "desactivado"
    flash(f"Usuario {estado_texto} correctamente.", "success")
    return redirect(url_for("usuarios_list"))

# ======================== MAIN ========================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        with app.app_context():
            init_db()
        print("Base de datos inicializada.")
    else:
        app.run(debug=True)
