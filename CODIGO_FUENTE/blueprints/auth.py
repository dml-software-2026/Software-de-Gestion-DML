import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from CODIGO_FUENTE.decorators import get_current_user, login_required
from CODIGO_FUENTE.extensions import get_db

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        logger.debug("Intento de login para email: %s", email)

        if not email or not password:
            flash("Email y contraseña son requeridos.", "error")
            return render_template("login.html")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()

        logger.debug("Usuario encontrado: %s", user is not None)

        if user:
            pwd_match = check_password_hash(user["password_hash"], password)
            logger.debug("Contraseña coincide: %s", pwd_match)

            if pwd_match:
                if not user["is_active"]:
                    flash("Usuario desactivado.", "error")
                    return render_template("login.html")
                session["user_id"] = user["id"]
                session["role"] = user["role"]  # CRÍTICO: Guardar rol en sesión
                session.modified = True
                flash(f"Bienvenido {email}", "success")
                logger.info("Sesión creada para user_id=%s, role=%s", user["id"], user["role"])
                return redirect(url_for("auth.index"))

        flash("Credenciales inválidas.", "error")
        logger.warning("Intento de login fallido para email: %s", email)

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

    return render_template("index.html", user=user)
 