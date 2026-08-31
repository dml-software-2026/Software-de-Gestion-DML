# CODIGO_FUENTE/blueprints/notificaciones.py
from flask import Blueprint, flash, redirect, render_template, request, url_for

from CODIGO_FUENTE.decorators import login_required, role_required
from CODIGO_FUENTE.extensions import get_db

notificaciones_bp = Blueprint('notificaciones', __name__, url_prefix='/admin')

@notificaciones_bp.route('/notificaciones', methods=['GET'])
@login_required
@role_required("ADMIN")
def listar_notificaciones():
    db = get_db()
    destinatarios = db.execute(
        "SELECT id, email, nombre, activo FROM usuarios_notificaciones ORDER BY email"
    ).fetchall()
    return render_template('notificaciones.html', destinatarios=destinatarios)


@notificaciones_bp.route('/notificaciones/agregar', methods=['POST'])
@login_required
@role_required("ADMIN")
def agregar_notificacion():
    email = request.form.get('email', '').strip()
    nombre = request.form.get('nombre', '').strip()
    if not email:
        flash("El email es obligatorio.", "error")
        return redirect(url_for('notificaciones.listar_notificaciones'))

    db = get_db()
    row = db.execute(
        "INSERT INTO usuarios_notificaciones (email, nombre, activo) VALUES (%s, %s, TRUE) "
        "ON CONFLICT (email) DO NOTHING RETURNING id",
        (email, nombre)
    ).fetchone()
    db.commit()

    if row:
        flash(f"Destinatario {email} agregado.", "success")
    else:
        flash(f"{email} ya estaba en la lista.", "info")
    return redirect(url_for('notificaciones.listar_notificaciones'))


@notificaciones_bp.route('/notificaciones/<int:id>/toggle', methods=['POST'])
@login_required
@role_required("ADMIN")
def toggle_notificacion(id):
    db = get_db()
    row = db.execute(
        "UPDATE usuarios_notificaciones SET activo = NOT activo WHERE id = %s RETURNING email, activo",
        (id,)
    ).fetchone()
    db.commit()

    if row:
        estado = "activado" if row['activo'] else "desactivado"
        flash(f"{row['email']} {estado}.", "success")
    return redirect(url_for('notificaciones.listar_notificaciones'))


@notificaciones_bp.route('/notificaciones/<int:id>/eliminar', methods=['POST'])
@login_required
@role_required("ADMIN")
def eliminar_notificacion(id):
    db = get_db()
    row = db.execute("DELETE FROM usuarios_notificaciones WHERE id = %s RETURNING email", (id,)).fetchone()
    db.commit()

    if row:
        flash(f"Destinatario {row['email']} eliminado.", "success")
    return redirect(url_for('notificaciones.listar_notificaciones'))