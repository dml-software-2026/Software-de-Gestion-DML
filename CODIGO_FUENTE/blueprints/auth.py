from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from CODIGO_FUENTE.extensions import get_db
from decorators import login_required, get_current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
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
                session["role"] = user["role"]  # CRÍTICO: Guardar rol en sesión
                session.modified = True
                flash(f"Bienvenido {email}", "success")
                print(f"[LOGIN] Sesion creada para user_id: {user['id']}, role: {user['role']}")
                return redirect(url_for("auth.index"))

        flash("Credenciales inválidas.", "error")
        print(f"[LOGIN] Credenciales rechazadas para {email}")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/")
@login_required
def index():
    user = get_current_user()

    # Validación de seguridad - si user es None, redirigir al login
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    db = get_db()

    def count(sql, params=()):
        return db.execute(sql, params).fetchone()['total']

    role = user['role']
    stats = {}

    if role == "RAYPAC":
        stats = {
            "equipos_registrados": count("SELECT COUNT(*) AS total FROM raypac_entries"),
            "equipos_sin_remito": count("SELECT COUNT(*) AS total FROM raypac_entries WHERE numero_remito IS NULL OR numero_remito = ''"),
            "envios_pendientes": count("SELECT COUNT(*) AS total FROM envios_repuestos WHERE estado_envio = 'ENVIADO'"),
            "tickets_activos": count("SELECT COUNT(*) AS total FROM tickets WHERE estado = 'ACTIVO'")
        }
    elif role == "DML_REPUESTOS":
        stats = {
            "stock_bajo": count("SELECT COUNT(*) AS total FROM stock_ubicaciones WHERE ubicacion = 'DML' AND cantidad <= 2"),
            "envios_pendientes": count("SELECT COUNT(*) AS total FROM envios_repuestos WHERE estado = 'PENDIENTE'"),
            "fichas_espera_repuestos": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion = 'A LA ESPERA DE REPUESTOS'"),
            "tickets_activos": count("SELECT COUNT(*) AS total FROM tickets WHERE estado != 'CERRADO'")
        }
    elif role == "DML_ST":
        # Equipos freezados en RAYPAC (con remito) sin ficha DML creada = pendientes de recepción
        try:
            equipos_pendientes = db.execute("""
                SELECT COUNT(*) AS total
                FROM raypac_entries r
                WHERE r.is_frozen = 1
                AND r.numero_remito IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM dml_fichas f WHERE f.raypac_id = r.id)
            """).fetchone()['total']
        except:
            equipos_pendientes = 0

        # Tickets sin ficha (pendientes de revisión inicial)
        try:
            tickets_revision_inicial = db.execute("""
                SELECT COUNT(*) AS total
                FROM tickets
                WHERE estado = 'ACTIVO'
                AND ficha_id IS NULL
            """).fetchone()['total']
        except:
            tickets_revision_inicial = 0

        # Repuestos que estaban EN FALTA y ahora tienen stock disponible
        try:
            repuestos_disponibles = db.execute("""
                SELECT COUNT(DISTINCT dr.codigo_repuesto) AS total
                FROM dml_repuestos dr
                JOIN dml_fichas f ON f.id = dr.ficha_id
                JOIN stock_ubicaciones su ON su.codigo_repuesto = dr.codigo_repuesto AND su.ubicacion = 'DML'
                WHERE dr.en_falta = 1
                AND f.is_closed = 0
                AND su.cantidad >= dr.cantidad_utilizada
            """).fetchone()['total']
        except:
            repuestos_disponibles = 0

        # Envíos de repuestos pendientes de recibir desde RAYPAC
        # Verificar si existen las columnas nuevas primero
        try:
            columns = db.execute("PRAGMA table_info(envios_repuestos)").fetchall()
            column_names = [col['name'] for col in columns]

            if 'estado_envio' in column_names and 'is_frozen' in column_names and 'fecha_recepcion_dml' in column_names:
                envios_repuestos_pendientes = db.execute("""
                    SELECT COUNT(*) AS total
                    FROM envios_repuestos
                    WHERE estado_envio = 'ENVIADO' AND is_frozen = 1 AND fecha_recepcion_dml IS NULL
                """).fetchone()['total']
            else:
                # Fallback para esquema antiguo
                envios_repuestos_pendientes = db.execute("""
                    SELECT COUNT(*) AS total
                    FROM envios_repuestos
                    WHERE estado = 'PENDIENTE'
                """).fetchone()['total']
        except:
            envios_repuestos_pendientes = 0

        stats = {
            "tickets_revision_inicial": tickets_revision_inicial,
            "fichas_revision_inicial": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion LIKE 'A LA ESPERA DE REVISI_N' AND is_closed = 0"),
            "fichas_en_reparacion": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion LIKE 'EN REPARACI_N' AND is_closed = 0"),
            "fichas_espera_repuestos": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion = 'A LA ESPERA DE REPUESTOS' AND is_closed = 0"),
            "fichas_listas": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion LIKE 'M_QUINA LISTA PARA RETIRAR' AND is_closed = 0"),
            "equipos_raypac_pendientes": equipos_pendientes,
            "envios_repuestos_pendientes": envios_repuestos_pendientes,
            "tickets_activos": count("SELECT COUNT(*) AS total FROM tickets WHERE estado != 'CERRADO'"),
            "repuestos_disponibles": repuestos_disponibles
        }
    else:  # ADMIN
        stats = {
            "equipos_raypac": count("SELECT COUNT(*) AS total FROM raypac_entries"),
            "fichas_abiertas": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE is_closed = 0"),
            "envios_pendientes": count("SELECT COUNT(*) AS total FROM envios_repuestos WHERE estado = 'PENDIENTE'"),
            "stock_bajo_total": count("SELECT COUNT(*) AS total FROM stock_ubicaciones WHERE cantidad <= 2")
        }

    return render_template("index.html", user=user, stats=stats)
