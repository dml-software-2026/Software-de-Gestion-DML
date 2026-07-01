from functools import wraps

from flask import session, redirect, url_for, flash

from extensions import get_db


def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def get_current_user_jinja():
    """Obtiene usuario actual para uso en Jinja2 (mismo resultado que get_current_user)."""
    return get_current_user()


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


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        # Validar que el usuario exista en BD
        user = get_current_user()
        if not user:
            session.clear()
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def permission_required(read_roles=None, write_roles=None):
    """
    Decorator para control de permisos granular.
    - read_roles: roles que pueden VER (lectura)
    - write_roles: roles que pueden EDITAR (escritura)
    Si solo se pasa write_roles, automáticamente tienen read también.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))
            user = get_current_user()
            if not user:
                session.clear()
                return redirect(url_for("auth.login"))

            user_role = user["role"]

            # ADMIN siempre tiene acceso completo
            if user_role == "ADMIN":
                return view(*args, **kwargs)

            # Verificar permisos de escritura (incluye lectura)
            if write_roles and user_role in write_roles:
                return view(*args, **kwargs)

            # Verificar permisos de solo lectura
            if read_roles and user_role in read_roles:
                kwargs['readonly'] = True
                return view(*args, **kwargs)

            flash("No tienes permiso para acceder a esta página.", "error")
            return redirect(url_for("auth.index"))
        return wrapped
    return decorator


def role_required(*roles):
    """Compatibilidad con código antiguo - todos tienen escritura."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))
            user = get_current_user()
            if not user:
                session.clear()
                return redirect(url_for("auth.login"))
            if user["role"] not in roles:
                flash("No tienes permiso para acceder a esta página.", "error")
                return redirect(url_for("auth.index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator
