import os
import sys
from io import BytesIO

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.decorators import (
    get_current_user,
    log_action,
    login_required,
    role_required,
)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.backup import generar_backup_zip
from CODIGO_FUENTE.services.carga_stock import PLANILLA_STOCK, cargar_stock_dml, leer_planilla_stock

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ======================== USUARIOS ========================

@admin_bp.route("/usuarios")
@login_required
@role_required("ADMIN")
def usuarios_list():
    db = get_db()
    user = get_current_user()
    usuarios = db.execute("SELECT * FROM users ORDER BY email").fetchall()
    return render_template("usuarios_list.html", usuarios=usuarios, user=user)


@admin_bp.route("/cargar-stock-csv", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def cargar_stock_desde_web():
    """Carga masiva del stock de DML desde la planilla del cliente (#310).

    GET solo muestra la pantalla; la carga se hace con el botón (POST), porque
    pisa las cantidades y ubicaciones de DML.
    """
    user = get_current_user()
    ruta = current_app.config.get("PLANILLA_STOCK", PLANILLA_STOCK)
    nombre_planilla = os.path.basename(ruta)
    if request.method == "GET":
        return render_template("cargar_stock.html", planilla=nombre_planilla,
                               existe=os.path.exists(ruta), resultado=None)

    db = get_db()
    try:
        filas, errores = leer_planilla_stock(ruta)
        resultados = cargar_stock_dml(db, filas)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[STOCK] ❌ Error en la carga masiva: {type(e).__name__}: {e!s}", file=sys.stderr, flush=True)
        log_action(user['id'], "CARGA_CSV", "matriz_repuestos", None, None,
                   f"resultado=error, planilla={nombre_planilla}, motivo={type(e).__name__}: {e!s}")
        flash(f"No se cargó nada: {e!s}", "error")
        return redirect(url_for("admin.cargar_stock_desde_web"))

    # Auditoría por fila (#213), después del commit de negocio: si una falla, no corta a las demás.
    fallos_auditoria = []
    for codigo, item, record_id, resultado in resultados:
        try:
            log_action(user['id'], "CARGA_CSV", "matriz_repuestos", record_id, None,
                       f"{codigo} - {item}, resultado={resultado}, planilla={nombre_planilla}")
        except Exception:
            fallos_auditoria.append(codigo)
    for numero_fila, codigo, motivo in errores:
        try:
            log_action(user['id'], "CARGA_CSV", "matriz_repuestos", None, None,
                       f"{codigo}, resultado=error, fila={numero_fila}, motivo={motivo}")
        except Exception:
            fallos_auditoria.append(codigo)
    if fallos_auditoria:
        flash(f"Carga completada, pero {len(fallos_auditoria)} fila(s) no pudieron auditarse: "
              f"{', '.join(fallos_auditoria)}", "warning")

    resultado = {
        "nuevos": [r[0] for r in resultados if r[3] == "nuevo"],
        "actualizados": sum(1 for r in resultados if r[3] == "actualizado"),
        "en_cero": sum(1 for f in filas if f["cantidad"] == 0),
        "errores": errores,
    }
    print(f"[STOCK] Carga masiva: {len(resultado['nuevos'])} nuevos, {resultado['actualizados']} actualizados, "
          f"{len(errores)} errores", file=sys.stderr, flush=True)
    return render_template("cargar_stock.html", planilla=nombre_planilla, existe=True, resultado=resultado)


@admin_bp.route("/usuarios/nueva", methods=["GET", "POST"])
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

            existe = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
            if existe:
                flash("Este email ya existe.", "error")
                return render_template("usuario_form.html", roles=roles)

            hash_pwd = generate_password_hash(password)
            db.execute("""
                INSERT INTO users (email, password_hash, nombre, role, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (email, hash_pwd, nombre, role))
            db.commit()

            log_action(user['id'], "CREATE", "users", None, None, f"{email} - {role}")

            flash(f"Usuario {email} creado.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except Exception as e:
            flash(f"Error: {e!s}", "error")

    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_form.html", roles=roles)


@admin_bp.route("/usuarios/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_edit(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = %s", (id,)).fetchone()

    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.usuarios_list"))

    if request.method == "POST":
        try:
            role = request.form.get("role")
            new_password = (request.form.get("password") or "").strip()

            if not role:
                flash("Selecciona un rol.", "error")
                return redirect(url_for("admin.usuario_edit", id=id))

            if new_password:
                hash_pwd = generate_password_hash(new_password)
                db.execute(
                    "UPDATE users SET role = %s, password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (role, hash_pwd, id)
                )
            else:
                db.execute(
                    "UPDATE users SET role = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (role, id)
                )
            db.commit()

            log_action(user['id'], "UPDATE", "users", id, None, f"{usuario['email']}")

            if new_password:
                flash("Usuario actualizado y contraseña cambiada.", "success")
            else:
                flash("Usuario actualizado.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except Exception as e:
            flash(f"Error: {e!s}", "error")

    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_edit.html", target_user=usuario, roles=roles)


@admin_bp.route("/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
@role_required("ADMIN")
def usuario_toggle(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = %s", (id,)).fetchone()

    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.usuarios_list"))

    # is_active ahora es BOOLEAN en Postgres (antes era INTEGER 0/1 en
    # SQLite), por eso el toggle pasó de "1 - valor" a un "not" simple.
    nuevo_estado = not usuario['is_active']
    db.execute("UPDATE users SET is_active = %s WHERE id = %s", (nuevo_estado, id))
    db.commit()

    log_action(user['id'], "TOGGLE", "users", id, str(usuario['is_active']), str(nuevo_estado))

    estado_texto = "activado" if nuevo_estado else "desactivado"
    flash(f"Usuario {estado_texto} correctamente.", "success")
    return redirect(url_for("admin.usuarios_list"))


# ======================== BACKUP (#52) ========================

@admin_bp.route("/backup")
@login_required
@role_required("ADMIN")
def backup():
    db = get_db()
    # Última descarga, para que se note si hace mucho que nadie hace backup.
    # log_action guarda la acción real como "[BACKUP] ..." en new_value.
    ultimo = db.execute("""
        SELECT l.fecha_hora AT TIME ZONE 'America/Argentina/Buenos_Aires' AS fecha, u.nombre, u.email
        FROM logs_auditoria l
        LEFT JOIN users u ON u.id = l.id_usuario
        WHERE l.tabla_afectada = 'backup'
        ORDER BY l.fecha_hora DESC
        LIMIT 1
    """).fetchone()
    return render_template("backup.html", ultimo=ultimo)


@admin_bp.route("/backup/descargar")
@login_required
@role_required("ADMIN")
def backup_descargar():
    user = get_current_user()
    db = get_db()
    try:
        nombre, contenido = generar_backup_zip(db)
    except Exception as e:
        print(f"❌ Error generando backup: {type(e).__name__}: {e!s}", file=sys.stderr, flush=True)
        flash("No se pudo generar el backup. Avisá al equipo de desarrollo.", "error")
        return redirect(url_for("admin.backup"))

    log_action(user['id'], "BACKUP", "backup", None, None, nombre)
    return send_file(BytesIO(contenido), mimetype="application/zip",
                     as_attachment=True, download_name=nombre)
